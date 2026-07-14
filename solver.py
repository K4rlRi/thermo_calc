import pandas as pd

from models.thermal_objects import *
from support.visualization import plot_cycle_history

class TransientCycleSolver:
    """Advances a vapor-compression cycle built from two ChargeVolumes - the
    condenser's and the evaporator's own refrigerant holdup (the high and low
    side of the cycle) - plus the compressor and expansion valve, which meter
    mass/energy between them but hold no state of their own (following Chi &
    Didion, Int. J. Refrigeration 5(3), 1982: pressure is derived per-volume
    from density and internal energy, not integrated as an independent
    ideal-gas guess). All flows for a step are computed from the *start-of-step*
    state of both volumes (consistent explicit Euler), then integrated once -
    unlike a sequential block-by-block sweep, no component sees another
    component's already-updated state from within the same step.
    """
    def __init__(self, compressor: Compressor, condenser: HeatExchanger, valve: ExpansionValve,
                 evaporator: HeatExchanger, condenser_volume: ChargeVolume, evaporator_volume: ChargeVolume):
        self.compressor = compressor
        self.condenser = condenser
        self.valve = valve
        self.evaporator = evaporator
        self.condenser_volume = condenser_volume
        self.evaporator_volume = evaporator_volume
        self.time = 0.0
        self.history = {"time": [], "p_cond": [], "t_cond": [], "p_evap": [], "t_evap": [],
                         "t_cond_water": [], "t_evap_water": [], "m_comp": [], "m_valve": []}

    def step(self, dt: float, verbose: bool = True):
        high, low = self.condenser_volume, self.evaporator_volume

        # 1. Mass flows and the enthalpy each stream carries, evaluated once at
        # the state of both volumes at the start of this step.
        m_comp, h_discharge = self.compressor.flows(low, high)
        m_valve = self.valve.flows(high, low)

        # 2. Heat exchanged with the secondary loops (also integrates the
        # secondary-side bulk states by dt). Pass the average of in/out
        # refrigerant flow through each volume - needed for the single-phase
        # effectiveness-NTU branch (Chi & Didion's w-bar).
        qdot_cond = self.condenser.exchange(high, (m_comp + m_valve) / 2.0, dt)
        qdot_evap = self.evaporator.exchange(low, (m_comp + m_valve) / 2.0, dt)

        # 3. Net mass/energy balance for each shared volume. The compressor
        # adds mass to the high side and removes it from the low side; the
        # valve does the reverse. Qdot is refrigerant -> secondary, so it is
        # subtracted from the refrigerant side's energy.
        dm_high_dt = m_comp - m_valve
        dU_high_dt = m_comp * h_discharge - m_valve * high.h - qdot_cond

        dm_low_dt = m_valve - m_comp
        dU_low_dt = m_valve * high.h - m_comp * low.h - qdot_evap

        # 4. Integrate both volumes.
        high.integrate(dm_high_dt, dU_high_dt, dt)
        low.integrate(dm_low_dt, dU_low_dt, dt)

        self.time += dt

        self.history["time"].append(self.time)
        self.history["p_cond"].append(high.p)
        self.history["t_cond"].append(high.t)
        self.history["p_evap"].append(low.p)
        self.history["t_evap"].append(low.t)
        self.history["t_cond_water"].append(self.condenser.state2.t)
        self.history["t_evap_water"].append(self.evaporator.state2.t)
        self.history["m_comp"].append(m_comp)
        self.history["m_valve"].append(m_valve)

        if verbose:
            print(f"Time: {self.time:.3f}s | Condenser: {high.p/1e5:.2f} bar, {high.t-273.15:.1f} °C "
                  f"| Evaporator: {low.p/1e5:.2f} bar, {low.t-273.15:.1f} °C "
                  f"| Cond water: {self.condenser.state2.t-273.15:.1f} °C | Evap water: {self.evaporator.state2.t-273.15:.1f} °C "
                  f"| m_comp: {m_comp:.4f} kg/s | m_valve: {m_valve:.4f} kg/s")

    def get_history(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)

    def show_history(self):
        """User-facing API to plot the recorded trajectories."""
        plot_cycle_history(self.get_history(), title="Heat Pump Cycle - Transient Response")
