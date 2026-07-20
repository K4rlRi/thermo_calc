import math
import CoolProp.CoolProp as CP
import pandas as pd

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

class FlowNode:
    def __init__(self, name: str = None):
        # Fall back to the class name (e.g., "Compressor") if no custom name is given
        self.name = name or self.__class__.__name__

    def save_to_history(self):
        """Every child should override this."""
        raise NotImplementedError("Subclasses of FlowNode must implement the saving method.")

    def get_history(self):
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

class ChargeVolume(FlowNode):
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
                 max_relative_step: float = 0.3, name: str = None):
        self.name = name or "ChargeVolume"
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
        self.q = None
        self._refresh_derived_state()

        # Graph-edge bookkeeping. A ChargeVolume never restricts flow on its own
        # (only Compressor/ExpansionValve do that) - it just records what arrives
        # and exposes the same rate as m_flow for whichever edge comes after it.
        self.m_dot_in = 0.0
        self.m_dot_out = 0.0
        self.h_in = self.h
        self.out_charge: FlowNode = None

        self.history = [self.current_state]

    @property
    def current_state(self) -> dict:
        return {
            f"{self.name}_p": self.p,
            f"{self.name}_t": self.t,
            f"{self.name}_h": self.h,
        }

    def save_to_history(self):
        self.history.append(self.current_state)

    def _refresh_derived_state(self):
        rho = self.m / self.volume
        u = self.U / self.m
        self.p = CP.PropsSI('P', 'D', rho, 'U', u, self.fluid)
        self.t = CP.PropsSI('T', 'D', rho, 'U', u, self.fluid)
        self.h = CP.PropsSI('H', 'D', rho, 'U', u, self.fluid)
        self.q = CP.PropsSI('Q', 'D', rho, 'U', u, self.fluid)


    def __call__(self, in_charge: FlowNode| ChargeVolume, out_charge: FlowNode| ChargeVolume, dt: float):
        """Record the inflow arriving from the previous edge in the ring and pass
        it straight through as this node's own m_flow, for whichever edge comes
        next to read - this only reflects what a non-metering node does; the
        actual accumulation happens in integrate(), once every block's output
        for this step is known."""
        if isinstance(in_charge, FlowNode):
            self.m_dot_in = in_charge.m_flow
        else:
            self.m_dot_in = in_charge.m_dot_out
        self.m_dot_out = self.m_dot_in
        self.h_in = in_charge.h
        self.out_charge = out_charge

        

    def integrate(self, dt: float):
        # Bounded to a maximum fractional change per step, same rationale as the
        # earlier Compressor/ExpansionValve fixes: mismatched component sizing (or
        # an early transient far from the eventual operating point) can otherwise
        # swing m/U by a large factor in a single explicit-Euler step.
        if isinstance(self.out_charge, FlowNode):
            m_dot_out = self.out_charge.m_flow
        else: 
            m_dot_out = self.out_charge.m_dot_in

        dm_dt = self.m_dot_in - m_dot_out
        # Energy leaving is carried at *this* volume's own bulk enthalpy (well-mixed
        # assumption); energy entering is carried at the upstream stream's enthalpy.
        dU_dt = self.m_dot_in * self.h_in - m_dot_out * self.h

        max_dm = self.max_relative_step * self.m
        dm = dm_dt * dt
        dm = max(-max_dm, min(dm, max_dm))
        self.m = max(self.m + dm, 1e-6)  # keep strictly positive: U/m and m/V must stay defined

        max_dU = self.max_relative_step * abs(self.U)
        dU = dU_dt * dt
        if max_dU > 0:
            dU = max(-max_dU, min(dU, max_dU))
        self.U = self.U + dU

        self._refresh_derived_state()


class HeatExchanger(FlowNode):
    """Heat exchange between one side of the refrigerant charge (a ChargeVolume)
    and a lumped, dynamically-integrated secondary fluid node.

    Single lumped zone: it does not resolve superheat/condensing/subcooling as
    separate regions along the exchanger.
    """
    def __init__(self, area: float, k_value: float, secondary_mass: float,
                 boundary_condition: FluidState, pipe_kv: float = 0.0007, name='HeatExchanger'):
        super().__init__(name or "HeatExchanger")
        self.ua = area * k_value
        self.secondary_mass = secondary_mass  # kg, secondary fluid charge held up in the exchanger
        self.reservoir_in = boundary_condition  # fixed upstream supply condition of the secondary loop (t_in, p, m_flow)
        self.reservoir_out = boundary_condition.copy()  # evolving secondary-side bulk/outlet node
        self.pipe_kv = pipe_kv  # flow coefficient of the connecting tube; large relative to ExpansionValve.kv
        self.m_flow = 0.0
        self.h = 0.0
        self.qdot = 0.0

        self.history = [self.current_state]

    @property
    def current_state(self) -> dict:
        return {
            f"{self.name}_mdot": self.m_flow,
            f"{self.name}_qdot": self.qdot,
            f"{self.name}_h": self.h,
            f"{self.name}_t_secondary_in": self.reservoir_in.t,
            f"{self.name}_t_secondary_out": self.reservoir_out.t
        }

    def save_to_history(self):
        self.history.append(self.current_state)


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

    def __call__(self, in_charge: ChargeVolume, out_charge: ChargeVolume, dt: float):
        """Advance the secondary-side bulk state by dt and set this node's own
        m_flow/h (the refrigerant leaving toward out_charge).

        Sign convention for qdot: positive means heat flows *into* the
        refrigerant (the standard thermodynamic convention, Q > 0 when heat is
        added to the system) - so a condenser (rejecting heat) shows negative
        qdot, an evaporator (absorbing heat) shows positive qdot.

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
        reservoir_out, reservoir_in = self.reservoir_out, self.reservoir_in
        t_refr_in, t_reservoir_out = in_charge.t, reservoir_out.t

        average_delta_t = t_reservoir_out - t_refr_in

        # The connecting tube has real, if very low, flow resistance - a pure
        # pass-through would make the *upstream* ChargeVolume's own mass balance
        # identically zero (whatever flows in is defined to instantly flow back
        # out again), freezing its density forever at its initial guess
        # regardless of what the rest of the loop does. pipe_kv is chosen large
        # relative to ExpansionValve.kv so this barely restricts flow in normal
        # operation, but a real (small) pressure difference between the two
        # flanking volumes now drives a real, computable mass flow instead.
        delta_p = in_charge.p - out_charge.p
        density_ref = CP.PropsSI('D', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)
        m_flow_refrigerant = math.copysign(self.pipe_kv * math.sqrt(abs(delta_p) * density_ref), delta_p)
        m_flow_magnitude = max(abs(m_flow_refrigerant), 1e-6)

        quality = CP.PropsSI('Q', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)

        if 0.0 <= quality <= 1.0: # if two phase, infinite heat capacity (cp)
            qdot = self.ua * average_delta_t  # W
        else: # single phase, heat capacity calculated from state
            cp1 = CP.PropsSI('C', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)
            c1 = max(m_flow_magnitude * cp1, 1e-6)
            epsilon = 1.0 - math.exp(-self.ua / c1)
            qdot = epsilon * c1 * average_delta_t
        self.qdot = qdot

        m_dot_reservoir_in = reservoir_in.m_flow

        # Open control-volume energy balance for the secondary node: net heat duty
        # (secondary loses what the refrigerant gains, hence -qdot) plus
        # convective exchange with the reservoir flow feeding it.
        dh_dt_reservoir = (-qdot + m_dot_reservoir_in * (reservoir_in.h - reservoir_out.h)) / self.secondary_mass
        h_reservoir_new = self._clamp_to_equilibrium(reservoir_out.p, reservoir_out.h, reservoir_out.h + dh_dt_reservoir * dt, t_refr_in, reservoir_out.fluid)

        reservoir_out.update_from_ph(reservoir_out.p, h_reservoir_new)
        reservoir_out.m_flow = m_dot_reservoir_in

        h_refrig_out = in_charge.h + (qdot / m_flow_magnitude)

        # Clamp outlet enthalpy to prevent unphysical subcooling/superheating past secondary fluid temp
        h_refrig_out = self._clamp_to_equilibrium(in_charge.p, in_charge.h, h_refrig_out, t_reservoir_out, in_charge.fluid)

        # Populate graph edge outputs for the solver - a specific enthalpy (J/kg),
        # same units every other block uses for .h. m_flow is signed: negative
        # means the pipe is momentarily carrying net mass back from out_charge
        # toward in_charge.
        self.m_flow = m_flow_refrigerant
        self.h = h_refrig_out


class Compressor(FlowNode):
    """Meters refrigerant from the low-side ChargeVolume into the high-side
    ChargeVolume. No longer owns a pressure state of its own: pressure is a
    property of the shared ChargeVolume it feeds."""
    def __init__(self, displacement: float, isentropic_efficiency: float = 0.8,
                 speed_rpm: float = 2900, name='Compressor'):
        super().__init__(name or "Compressor")
        self.displacement = displacement  # m^3/rev
        self.eta_s = isentropic_efficiency
        self.speed_rpm = speed_rpm
        self.power_consumed = 0
        self.m_flow = 0.0
        self.h = 0.0

        self.history = [self.current_state]

    @property
    def current_state(self) -> dict:
        return {
            f"{self.name}_mdot": self.m_flow,
            f"{self.name}_power_consumed": self.power_consumed,
            f"{self.name}_h": self.h,
            f"{self.name}_speed_rpm": self.speed_rpm,
        }

    def save_to_history(self):
        self.history.append(self.current_state)

    def __call__(self, in_charge: ChargeVolume, out_charge: ChargeVolume, dt: float):
        """Sets m_flow/h: mass leaves in_charge (the suction/low-pressure side,
        carrying in_charge.h) and enters out_charge (the discharge/high-pressure
        side, carrying the compressed enthalpy) at this instant."""
        speed_rps = self.speed_rpm / 60.0
        density_in = CP.PropsSI('D', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)

        # Volumetric efficiency drops toward zero as the compression ratio grows -
        # the stabilizing feedback a real compressor has: it throttles its own
        # throughput back down instead of continuing to force mass into an
        # already-overpressured high side.
        pressure_ratio = out_charge.p / max(in_charge.p, 1e5)
        vol_efficiency = max(0.0, min(0.95, 0.95 - 0.05 * pressure_ratio))

        m_flow = self.displacement * speed_rps * density_in * vol_efficiency

        s_in = CP.PropsSI('S', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)
        h_ideal = CP.PropsSI('H', 'P', out_charge.p, 'S', s_in, in_charge.fluid)
        h_real = in_charge.h + (h_ideal - in_charge.h) / self.eta_s

        self.power_consumed = m_flow * (h_real - in_charge.h)
        self.m_flow = m_flow
        self.h = h_real


class ExpansionValve(FlowNode):
    """Meters refrigerant from the high-side ChargeVolume into the low-side
    ChargeVolume via isenthalpic throttling. No longer owns a pressure state
    of its own: pressure is a property of the shared ChargeVolume it feeds."""
    def __init__(self, flow_coefficient: float, name='ExpansionValve'):
        super().__init__(name or "ExpansionValve")
        self.kv = flow_coefficient    # Valve sizing flow coefficient
        self.m_flow = 0.0
        self.h = 0.0

        self.history = [self.current_state]

    @property
    def current_state(self) -> dict:
        return {
            f"{self.name}_mdot": self.m_flow,
            f"{self.name}_h": self.h,
        }

    def save_to_history(self):
        self.history.append(self.current_state)

    def __call__(self, in_charge: ChargeVolume, out_charge: ChargeVolume, dt: float):
        """Sets m_flow/h: mass leaves in_charge (high pressure) and enters
        out_charge (low pressure), both carrying in_charge.h (isenthalpic
        throttling)."""
        density_in = CP.PropsSI('D', 'P', in_charge.p, 'H', in_charge.h, in_charge.fluid)
        pressure_drop = max(in_charge.p - out_charge.p, 1000.0)  # guard against negative square roots
        self.m_flow = self.kv * math.sqrt(pressure_drop * density_in)
        self.h = in_charge.h
