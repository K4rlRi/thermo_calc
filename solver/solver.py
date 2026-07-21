import pandas as pd
from pathlib import Path

from models.thermal_objects import *
from support.visualization import plot_cycle_history

class TransientCycleSolver:
    """Euler based step whise cycle calculations. """
    def __init__(self, block_list: list):
        self.block_list = block_list    
        self.time = 0.0
        self.dt = 0.0
        self.time_history = [self.time]

    def step(self, dt: float, verbose: bool = False):
        self.dt = dt
        n = len(self.block_list)

        for i, block in enumerate(self.block_list):
            in_charge = self.block_list[i - 1]
            out_charge = self.block_list[(i + 1) % n]
            block(in_charge, out_charge, dt)

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

    def solve(self, n_steps: float, dt = float, stats_every: int = 100):
        for i in range(n_steps):
            self.step(dt=dt, verbose=(i % stats_every == 0 ))


    def get_full_history(self) -> pd.DataFrame:
        all_component_df = pd.concat([block.get_history() for block in self.block_list], axis=1)
        all_component_df.index = pd.Index(self.time_history, name="time")
        return all_component_df

    def save_full_history(self, filename = "sim_history", filepath = Path.cwd()):
        full_history_df = self.get_full_history()
        full_history_df.to_csv(filepath / f"{filename}.csv", index=True)

    def show_history(self):
        """User-facing API to plot the recorded trajectories."""
        plot_cycle_history(self.get_full_history(), title="Heat Pump Cycle - Transient Response")
