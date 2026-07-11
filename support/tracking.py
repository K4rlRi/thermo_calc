import pandas as pd
from models.thermal_objects import FluidState

class CycleTracker:
    def __init__(self):
        # Dictionary to hold history for each state point
        # Format: { "State 1": { "p": [], "t": [], "h": [], "s": [], "m_flow": [] }, ... }
        self.history = {}

    def log_state(self, state_name: str, state: FluidState):
        """Records the current values of a FluidState at a specific point."""
        if state_name not in self.history:
            self.history[state_name] = {"p": [], "t": [], "h": [], "s": [], "m_flow": []}
        
        self.history[state_name]["p"].append(state.p)
        self.history[state_name]["t"].append(state.t)
        self.history[state_name]["h"].append(state.h)
        self.history[state_name]["s"].append(state.s)
        self.history[state_name]["m_flow"].append(state.m_flow)

    def get_dataframe(self, state_name: str) -> pd.DataFrame:
        """Returns the history of a specific state point as a Pandas DataFrame."""
        if state_name in self.history:
            df = pd.DataFrame(self.history[state_name])
            df.index.name = "Iteration"
            return df
        return pd.DataFrame()