import pandas as pd
from pathlib import Path

from models.thermal_objects import *
from support.visualization import plot_cycle_history

class TransientCycleSolver:
    """Advances a vapor-compression cycle expressed as a ring of blocks:
    Compressor - ChargeVolume - HeatExchanger - ChargeVolume - ExpansionValve -
    ChargeVolume - HeatExchanger - ChargeVolume - (back to Compressor). Every
    block implements __call__(in_charge, out_charge, dt) and sets its own
    m_flow/h; ChargeVolume additionally integrates its mass/energy balance from
    the in/out flows once every block's output for the step is known
    (following Chi & Didion, Int. J. Refrigeration 5(3), 1982: pressure is
    derived per-volume from density and internal energy, not integrated as an
    independent ideal-gas guess).

    Step is a single sequential pass in list order, so every block's own
    ChargeVolume neighbours' state (p/h/t) is always current, and every
    ChargeVolume exposes the flow it just received as its own m_flow for
    whichever edge comes next to read - a ChargeVolume never meters flow
    itself, only Compressor and ExpansionValve do. Only one connection in the
    ring is unavoidably one step stale (the compressor's suction neighbour is
    processed last in the pass), the same staggering the very first sequential
    solver in this project used.
    """
    def __init__(self, block_list: list):
        self.block_list = block_list    
        self.time = 0.0
        self.dt = 0.0
        self.time_history = [self.time]

    def step(self, dt: float, verbose: bool = False):
        self.dt = dt
        n = len(self.block_list)

        # Phase 1: every block computes its own m_flow/h from its neighbours'
        # current state.
        for i, block in enumerate(self.block_list):
            in_charge = self.block_list[i - 1]
            out_charge = self.block_list[(i + 1) % n]
            block(in_charge, out_charge, dt)

        # Phase 2: integrate the ChargeVolumes now that every neighbour's
        # in/out flow for this step is known.
        for i, block in enumerate(self.block_list):
            if isinstance(block, ChargeVolume):
                block.integrate( dt)

        self.time += dt
        self.time_history.append(self.time)

        for block in self.block_list:
            block.save_to_history()

        if verbose:
            parts = [f"{b.name}: {b.p/1e5:.2f} bar, {b.t-273.15:.1f} °C, quality {b.q}"
                     for b in self.block_list if isinstance(b, ChargeVolume)]
            print(f"Time: {self.time:.3f}s | " + " | ".join(parts))

    def get_full_history(self) -> pd.DataFrame:
        all_component_df = pd.concat([block.get_history() for block in self.block_list], axis=1)
        # Time lives only on the solver (it's the one thing every block agrees
        # on), so it's stitched in here as the index rather than tracked
        # per-block - a standalone block.get_history() still just gets a plain
        # iteration count.
        all_component_df.index = pd.Index(self.time_history, name="time")
        return all_component_df

    def save_full_history(self, filename = "sim_history", filepath = Path.cwd()):
        full_history_df = self.get_full_history()
        full_history_df.to_csv(filepath / f"{filename}.csv", index=True)

    def show_history(self):
        """User-facing API to plot the recorded trajectories."""
        plot_cycle_history(self.get_full_history(), title="Heat Pump Cycle - Transient Response")
