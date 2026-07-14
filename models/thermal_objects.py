import math
import CoolProp.CoolProp as CP

from support.visualization import plot_component_history

class FluidState:
    def __init__(self, fluid_name: str):
        self.fluid = fluid_name
        self.p = None  # Pressure in Pa
        self.t = None  # Temperature in K
        self.h = None  # Specific Enthalpy in J/kg
        self.s = None  # Specific Entropy in J/kg·K
        self.m_flow = None  # Mass flow rate in kg/s
        self.cp = None  # Specific heat capacity in J/kg·K
        self.c_min = None
        self.quality = None


    def update_from_ph(self, p: float, h: float):
        """Update all properties using Pressure and Enthalpy."""
        self.p = p
        self.h = h
        self.t = CP.PropsSI('T', 'P', p, 'H', h, self.fluid)
        self.s = CP.PropsSI('S', 'P', p, 'H', h, self.fluid)
        self.cp = CP.PropsSI('C', 'P', p, 'H', h, self.fluid)
        self.c_min = self.m_flow * self.cp
        self.quality = CP.PropsSI('Q', 'P', p, 'H', h, self.fluid)

    def update_from_tp(self, t: float, p: float):
        """Update all properties using Pressure and Temperature."""
        self.p = p
        self.h = CP.PropsSI('H', 'T', t, 'P', p, self.fluid)
        self.t = t
        self.s = CP.PropsSI('S', 'T', t, 'P', p, self.fluid)
        self.cp = CP.PropsSI('C', 'P', p, 'H', self.h, self.fluid)
        self.c_min = self.m_flow * self.cp
        self.quality = CP.PropsSI('Q', 'P', p, 'H', self.h, self.fluid)


    def update_from_psat(self, p:float, quality:float):
        """Update properties at saturation (quality: 0 = liquid, 1 = vapor)."""

        assert quality <= 1.0 and quality >= 0.0
        self.p = p
        self.h = CP.PropsSI('H', 'P', p, 'Q', quality, self.fluid)
        self.t = CP.PropsSI('T', 'P', p, 'Q', quality, self.fluid)
        self.s = CP.PropsSI('S', 'P', p, 'Q', quality, self.fluid)
        self.cp = CP.PropsSI('C', 'P', p, 'Q', quality, self.fluid)
        self.c_min = self.m_flow * self.cp
        self.quality = quality


    def copy(self):
        new_state = FluidState(self.fluid)
        new_state.p, new_state.t, new_state.h, new_state.s, new_state.m_flow, new_state.quality = self.p, self.t, self.h, self.s, self.m_flow, self.quality
        return new_state

    def get_prop_value(self, property:str, quality: float):
        # if check_string(allowed= ['H','T','s']):

        property_value = CP.PropsSI(property, 'P', self.p, 'Q', quality, self.fluid)
        return property_value


    def get_c_min(self):
        return self.c_min

    def is_two_phase(self):
        return 0.0 < self.quality < 1.0

class ThermalObject:
    def __init__(self, name: str = None):
        # Fall back to the class name (e.g., "Compressor") if no custom name is given
        self.name = name or self.__class__.__name__
        self.history = {"p": [], "t": [], "h": [], "s": [], "m_flow": []}

    def get_history(self):
        import pandas as pd
        df = pd.DataFrame(self.history)
        df.index.name = "Iteration"
        return df

    def show_history(self):
        """User-facing API to trigger the auxiliary plotting tool."""
        df = self.get_history()
        # Call the standalone helper function
        plot_component_history(df, title=self.name)

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



class ChargeVolume:
    """Fixed-volume refrigerant accumulator (e.g. compressor manifold + condenser,
    or expansion valve + evaporator, lumped together as one 'side' of the cycle).

    This is what actually pins the cycle's high/low pressure to the refrigerant's
    real thermal state: total mass and internal energy are integrated from the
    flows crossing the volume's boundary, and pressure/temperature/enthalpy are
    *derived* from density (m/V) and specific internal energy (U/m) via CoolProp,
    rather than being pushed along an independent ideal-gas dp/dt guess. Because
    the energy balance includes whatever heat a HeatExchanger manages to move to
    or from the secondary loop, the saturation pressure this settles at is
    coupled to the secondary loop's actual temperature.
    """
    def __init__(self, fluid: str, volume: float, initial_p: float, initial_quality: float,
                 max_relative_step: float = 0.3):
        self.fluid = fluid
        self.volume = volume  # m^3, physical size of this side of the cycle
        self.max_relative_step = max_relative_step  # largest fractional change in m or U allowed per call

        rho = CP.PropsSI('D', 'P', initial_p, 'Q', initial_quality, fluid)
        u = CP.PropsSI('U', 'P', initial_p, 'Q', initial_quality, fluid)
        self.m = rho * volume
        self.U = u * self.m

        self.p = None  # Pa
        self.t = None  # K
        self.h = None  # J/kg, bulk specific enthalpy (well-mixed assumption: outlet state = bulk state)
        self._refresh_derived_state()

    def _refresh_derived_state(self):
        rho = self.m / self.volume
        u = self.U / self.m
        self.p = CP.PropsSI('P', 'D', rho, 'U', u, self.fluid)
        self.t = CP.PropsSI('T', 'D', rho, 'U', u, self.fluid)
        self.h = CP.PropsSI('H', 'D', rho, 'U', u, self.fluid)

    def integrate(self, dm_dt: float, dU_dt: float, dt: float):
        # Bounded to a maximum fractional change per step, same rationale as the
        # earlier Compressor/ExpansionValve fixes: mismatched component sizing (or
        # an early transient far from the eventual operating point) can otherwise
        # swing m/U by a large factor in a single explicit-Euler step.
        max_dm = self.max_relative_step * self.m
        dm = max(-max_dm, min(dm_dt * dt, max_dm))
        self.m = max(self.m + dm, 1e-6)  # keep strictly positive: U/m and m/V must stay defined

        max_dU = self.max_relative_step * abs(self.U)
        dU = dU_dt * dt
        if max_dU > 0:
            dU = max(-max_dU, min(dU, max_dU))
        self.U = self.U + dU

        self._refresh_derived_state()


class HeatExchanger(ThermalObject):
    """Heat exchange between one side of the refrigerant charge (a ChargeVolume)
    and a lumped, dynamically-integrated secondary fluid node.

    Single lumped zone: it does not resolve superheat/condensing/subcooling as
    separate regions along the exchanger.
    """
    def __init__(self, area: float, k_value: float, secondary_mass: float,
                 boundary_condition: FluidState, name='HeatExchanger'):
        super().__init__(name)
        self.ua = area * k_value
        self.secondary_mass = secondary_mass  # kg, secondary fluid charge held up in the exchanger
        self.reservoir2 = boundary_condition  # fixed upstream supply condition of the secondary loop (t_in, p, m_flow)
        self.state2 = boundary_condition.copy()  # evolving secondary-side bulk/outlet node

    def _clamp_to_equilibrium(self, p: float, h_prev: float, h_candidate: float, t_other: float, fluid: str) -> float:
        """Prevent an explicit-Euler step from overshooting past the instantaneous
        equilibrium enthalpy implied by the other stream's current temperature."""
        try:
            h_limit = CP.PropsSI('H', 'P', p, 'T', t_other, fluid)
        except ValueError:
            # t_other coincides with the saturation temperature at p (ambiguous quality) -
            # this only happens when the two streams are already nearly in equilibrium,
            # i.e. exactly when the risk of a large overshoot is smallest, so skip clamping.
            return h_candidate
        lo, hi = sorted((h_prev, h_limit))
        return min(max(h_candidate, lo), hi)

    def exchange(self, refrigerant_side: ChargeVolume, m_flow_refrigerant: float, dt: float) -> float:
        """Advance the secondary-side bulk state by dt and return Qdot (W),
        positive meaning heat flows from the refrigerant side to the secondary side.

        Follows Chi & Didion (Int. J. Refrigeration 5(3), 1982): while the
        refrigerant is two-phase its temperature is pinned near saturation
        (effectively infinite capacity rate), so heat transfer is plain
        conductance, UA*dT (their eq. 12). Once it's single-phase (superheated
        vapour / subcooled liquid), its own finite flow capacity now limits how
        much heat it can absorb/reject before its temperature moves - handled
        with effectiveness-NTU against that capacity (their eq. 11). Without
        this split, a superheated refrigerant stream keeps absorbing heat at
        the unbounded UA*dT rate and runs away instead of self-limiting.
        """
        state2, reservoir2 = self.state2, self.reservoir2
        t1, t2 = refrigerant_side.t, state2.t

        quality = CP.PropsSI('Q', 'P', refrigerant_side.p, 'H', refrigerant_side.h, refrigerant_side.fluid)
        if 0.0 <= quality <= 1.0:
            qdot = self.ua * (t1 - t2)  # W
        else:
            cp1 = CP.PropsSI('C', 'P', refrigerant_side.p, 'H', refrigerant_side.h, refrigerant_side.fluid)
            c1 = max(m_flow_refrigerant * cp1, 1e-6)
            epsilon = 1.0 - math.exp(-self.ua / c1)
            qdot = epsilon * c1 * (t1 - t2)

        m2_in = reservoir2.m_flow

        # Open control-volume energy balance for the secondary node: net heat duty
        # plus convective exchange with the reservoir flow feeding it.
        dh2_dt = (qdot + m2_in * (reservoir2.h - state2.h)) / self.secondary_mass
        h2_new = self._clamp_to_equilibrium(state2.p, state2.h, state2.h + dh2_dt * dt, t1, state2.fluid)

        state2.update_from_ph(state2.p, h2_new)
        state2.m_flow = m2_in

        return qdot


class Compressor(ThermalObject):
    """Meters refrigerant from the low-side ChargeVolume into the high-side
    ChargeVolume. No longer owns a pressure state of its own: pressure is a
    property of the shared ChargeVolume it feeds."""
    def __init__(self, displacement: float, isentropic_efficiency: float = 0.8,
                 speed_rpm: float = 2900, name='Compressor'):
        super().__init__(name)
        self.displacement = displacement  # m^3/rev
        self.eta_s = isentropic_efficiency
        self.speed_rpm = speed_rpm
        self.power_consumed = 0

    def flows(self, low_side: ChargeVolume, high_side: ChargeVolume) -> tuple:
        """Return (m_flow, h_discharge): mass leaves low_side (carrying
        low_side.h) and enters high_side (carrying h_discharge) at this instant."""
        speed_rps = self.speed_rpm / 60.0
        density_in = CP.PropsSI('D', 'P', low_side.p, 'H', low_side.h, low_side.fluid)

        # Volumetric efficiency drops toward zero as the compression ratio grows -
        # the stabilizing feedback a real compressor has: it throttles its own
        # throughput back down instead of continuing to force mass into an
        # already-overpressured high side.
        pressure_ratio = high_side.p / max(low_side.p, 1e5)
        vol_efficiency = max(0.0, min(0.95, 0.95 - 0.05 * pressure_ratio))

        m_flow = self.displacement * speed_rps * density_in * vol_efficiency

        s_in = CP.PropsSI('S', 'P', low_side.p, 'H', low_side.h, low_side.fluid)
        h_ideal = CP.PropsSI('H', 'P', high_side.p, 'S', s_in, low_side.fluid)
        h_real = low_side.h + (h_ideal - low_side.h) / self.eta_s

        self.power_consumed = m_flow * (h_real - low_side.h)

        return m_flow, h_real


class ExpansionValve(ThermalObject):
    """Meters refrigerant from the high-side ChargeVolume into the low-side
    ChargeVolume via isenthalpic throttling. No longer owns a pressure state
    of its own: pressure is a property of the shared ChargeVolume it feeds."""
    def __init__(self, flow_coefficient: float, name='ExpansionValve'):
        super().__init__(name)
        self.kv = flow_coefficient    # Valve sizing flow coefficient

    def flows(self, high_side: ChargeVolume, low_side: ChargeVolume) -> float:
        """Return m_flow: mass leaves high_side and enters low_side, both
        carrying high_side.h (isenthalpic throttling)."""
        density_in = CP.PropsSI('D', 'P', high_side.p, 'H', high_side.h, high_side.fluid)
        pressure_drop = max(high_side.p - low_side.p, 1000.0)  # guard against negative square roots

        return self.kv * math.sqrt(pressure_drop * density_in)
