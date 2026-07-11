import math
import CoolProp.CoolProp as CP

class FluidState:
    def __init__(self, fluid_name: str):
        self.fluid = fluid_name
        self.p = None  # Pressure in Pa
        self.t = None  # Temperature in K
        self.h = None  # Specific Enthalpy in J/kg
        self.s = None  # Specific Entropy in J/kg·K
        self.m_flow = None  # Mass flow rate in kg/s

    def update_from_ph(self, p: float, h: float):
        """Update all properties using Pressure and Enthalpy."""
        self.p = p
        self.h = h
        self.t = CP.PropsSI('T', 'P', p, 'H', h, self.fluid)
        self.s = CP.PropsSI('S', 'P', p, 'H', h, self.fluid)

    def update_from_psat(self, p:float, quality:float):
        """Update properties at saturation (quality: 0 = liquid, 1 = vapor)."""

        assert quality <= 1.0 and quality >= 0.0
        self.p = p
        self.h = CP.PropsSI('H', 'P', p, 'Q', quality, self.fluid)
        self.t = CP.PropsSI('T', 'P', p, 'Q', quality, self.fluid)
        self.s = CP.PropsSI('S', 'P', p, 'Q', quality, self.fluid)
        
    def copy(self):
        new_state = FluidState(self.fluid)
        new_state.p, new_state.t, new_state.h, new_state.s, new_state.m_flow = self.p, self.t, self.h, self.s, self.m_flow
        return new_state
    
    def get_prop_value(self, property:str, quality: float):
        # if check_string(allowed= ['H','T','s']):

        property_value = CP.PropsSI(property, 'P', self.p, 'Q', quality, self.fluid)
        return property_value


class ThermalObject:
    def __init__(self, name: str = None):
        # Fall back to the class name (e.g., "Compressor") if no custom name is given
        self.name = name or self.__class__.__name__
        self.history = {"p": [], "t": [], "h": [], "s": [], "m_flow": []}

    def pipe(self, state_in: FluidState) -> FluidState:
        """The master pipeline method. 
        Children do NOT override this; they override _calculate instead.
        """
        # 1. Execute the specific component physics
        state_out = self._calculate(state_in)
        
        # 2. Automatically track the resulting state internally
        self.history["p"].append(state_out.p)
        self.history["t"].append(state_out.t)
        self.history["h"].append(state_out.h)
        self.history["s"].append(state_out.s)
        self.history["m_flow"].append(state_out.m_flow)
        
        return state_out

    def _calculate(self, state_in: FluidState) -> FluidState:
        """Abstract-like method that child classes must implement."""
        raise NotImplementedError("Subclasses must implement the thermodynamic calculations in _calculate!")

    def get_history(self):
        import pandas as pd
        df = pd.DataFrame(self.history)
        df.index.name = "Iteration"
        return df

class SecondaryLoop:
    def __init__(self, fluid: str, m_flow: float, t_in: float, cp: float = 4184):
        self.fluid = fluid
        self.m_flow = m_flow  # kg/s
        self.t_in = t_in      # K (Input Temperature)
        self.t_out = t_in     # K (Output Temperature)
        self.cp = cp          # J/kg·K (Specific heat capacity)

        self.c_min = self.m_flow * self.cp
        

    def get_c_min(self):
        return self.c_min
    


class HeatExchanger(ThermalObject):
    def __init__(self, area: float, k_value: float, connected_loop: SecondaryLoop, name = 'HeatExchanger'):
        super().__init__(name)
        self.ua = area * k_value
        
        self.connected = connected_loop
        self.heat_transferred = 0

    def q_transfer(self, state_in:FluidState, q_max_fluid:float):

        c_min = self.connected.get_c_min()
        
        # 3. Calculate NTU and Effectiveness (epsilon)
        ntu = self.ua / c_min
        epsilon = 1.0 - math.exp(-ntu)
        
        # 4. Calculate Maximum Possible Heat Transfer (Q_max)
        # Based on the maximum temperature difference between the two entering streams
        t_in_refrigerant = state_in.t
        t_in_secondary = self.connected.t_in
        
        q_max_loop= c_min * abs(t_in_refrigerant - t_in_secondary)

        q_max = min(q_max_fluid, q_max_loop)
        q_actual = epsilon * q_max

        return q_actual

    def _calculate(self, state_in: FluidState) -> FluidState:
        state_out = state_in.copy()
        # Assume ideal condensation to saturated liquid (Q=0) at current high pressure

        # t_sat = state_in.get_prop_value('T', quality=)
        try:
            h_limit = CP.PropsSI('H', 'P', state_in.p, 'T', self.connected.t_in, state_in.fluid)
        except ValueError:
            # If the secondary loop temperature lands exactly inside the saturation dome,
            # fall back to saturated liquid (Q=0) for condenser or saturated vapor (Q=1) for evaporator
            target_q = 0.0 if state_in.t > self.connected.t_in else 1.0
            h_limit = CP.PropsSI('H', 'P', state_in.p, 'Q', target_q, state_in.fluid)


        q_max_fluid = state_in.m_flow * abs(state_in.h - h_limit)

        self.heat_transferred = self.q_transfer(state_in=state_in, q_max_fluid=q_max_fluid)

        if state_in.t > self.connected.t_in:
            # Condenser Mode
            h_out = state_in.h - (self.heat_transferred / state_in.m_flow)
            # Sign-safe boundary cushion (staying 0.5% above the floor enthalpy value)
            h_out = max(h_out, h_limit + abs(h_limit) * 0.005)
            self.connected.t_out = self.connected.t_in + (self.heat_transferred / self.connected.get_c_min())
        else:
            # Evaporator Mode
            h_out = state_in.h + (self.heat_transferred / state_in.m_flow)
            # Sign-safe boundary cushion (staying 0.5% below the ceiling enthalpy value)
            h_out = min(h_out, h_limit - abs(h_limit) * 0.005)
            self.connected.t_out = self.connected.t_in - (self.heat_transferred / self.connected.get_c_min())

        # Update the outgoing refrigerant state using the new enthalpy
        state_out.update_from_ph(state_in.p, h_out)
        return state_out
    

class Compressor(ThermalObject):
    def __init__(self, p_max: float, m_flow_max: float, isentropic_efficiency: float = 0.8, name = 'Compressor'):
        super().__init__(name)
        self.p_high = p_max  # Target high pressure in Pa
        self.eta_s = isentropic_efficiency
        self.power_consumed = 0

    def _calculate(self, state_in: FluidState) -> FluidState:
        state_out = state_in.copy()
        
        # 1. Ideal (isentropic) enthalpy at target high pressure
        h_ideal = CP.PropsSI('H', 'P', self.p_high, 'S', state_in.s, state_in.fluid)
        
        # 2. Real enthalpy using compressor efficiency
        h_real = state_in.h + (h_ideal - state_in.h) / self.eta_s
        
        state_out.update_from_ph(self.p_high, h_real)
        self.power_consumed = state_in.m_flow * (state_out.h - state_in.h)
        return state_out



class ExpansionValve(ThermalObject):
    def __init__(self, p_low: float, name = 'ExpansionValve'):
        super().__init__(name)
        self.p_low = p_low  # Target low pressure in Pa

    def pipe(self, state_in: FluidState) -> FluidState:
        state_out = state_in.copy()
        # An expansion valve is isenthalpic (h stays constant)
        state_out.update_from_ph(self.p_low, state_in.h)
        return state_out

