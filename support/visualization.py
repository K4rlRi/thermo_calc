# from support.tracking import *

import matplotlib.pyplot as plt
import pandas as pd

def plot_cycle_history(df: pd.DataFrame, title: str = "Heat Pump Cycle"):
    """Plot the transient trajectories of a TransientCycleSolver run: refrigerant
    and secondary-loop temperatures, refrigerant pressures, and mass flows vs time.

    Column names are discovered by prefix (p_<name>, t_<name>, t_secondary_<name>,
    m_flow_<name>) so this works for any block_list the solver was built with,
    not just a fixed condenser/evaporator pair.
    """
    if df.empty:
        print(f"No history data available to plot for {title}.")
        return

    p_cols = [c for c in df.columns if c.startswith("p_")]
    t_secondary_cols = [c for c in df.columns if c.startswith("t_secondary_")]
    t_cols = [c for c in df.columns if c.startswith("t_") and c not in t_secondary_cols]
    m_flow_cols = [c for c in df.columns if c.startswith("m_flow_")]

    fig, axs = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # 1. Pressures
    for c in p_cols:
        axs[0].plot(df["time"], df[c] / 1e5, label=c.removeprefix("p_"))
    axs[0].set_ylabel("Pressure (bar)")
    axs[0].set_title("Refrigerant pressure")
    axs[0].legend()
    axs[0].grid(True)

    # 2. Temperatures: refrigerant (solid) vs secondary loop (dashed)
    for c in t_cols:
        axs[1].plot(df["time"], df[c] - 273.15, label=c.removeprefix("t_"))
    for c in t_secondary_cols:
        axs[1].plot(df["time"], df[c] - 273.15, linestyle='--',
                    label=c.removeprefix("t_secondary_") + " (secondary)")
    axs[1].set_ylabel("Temperature (°C)")
    axs[1].set_title("Refrigerant vs secondary loop temperature")
    axs[1].legend()
    axs[1].grid(True)

    # 3. Mass flows
    for c in m_flow_cols:
        axs[2].plot(df["time"], df[c], label=c.removeprefix("m_flow_"))
    axs[2].set_ylabel("Mass flow (kg/s)")
    axs[2].set_xlabel("Time (s)")
    axs[2].set_title("Refrigerant mass flow")
    axs[2].legend()
    axs[2].grid(True)

    plt.tight_layout()
    plt.show()

def plot_component_history(df: pd.DataFrame, title: str):
    """Auxiliary function to plot thermodynamic states over iterations."""
    if df.empty:
        print(f"No history data available to plot for {title}.")
        return

    # Create a nice 2x2 grid of subplots
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"Convergence History: {title}", fontsize=16, fontweight='bold')

    # Convert absolute Temperatures to Celsius for better engineering readability
    t_celsius = df["t"] - 273.15
    # Convert Pa to bar for clean scales
    p_bar = df["p"] / 1e5

    # 1. Pressure Plot
    axs[0, 0].plot(df.index, p_bar, marker='o', color='crimson')
    axs[0, 0].set_title("Pressure")
    axs[0, 0].set_ylabel("Pressure (bar)")
    axs[0, 0].grid(True)

    # 2. Temperature Plot
    axs[0, 1].plot(df.index, t_celsius, marker='s', color='darkorange')
    axs[0, 1].set_title("Temperature")
    axs[0, 1].set_ylabel("Temperature (°C)")
    axs[0, 1].grid(True)

    # 3. Enthalpy Plot
    axs[1, 0].plot(df.index, df["h"] / 1e3, marker='^', color='teal')  # kJ/kg
    axs[1, 0].set_title("Specific Enthalpy")
    axs[1, 0].set_xlabel("Iteration")
    axs[1, 0].set_ylabel("Enthalpy (kJ/kg)")
    axs[1, 0].grid(True)

    # 4. Entropy Plot
    axs[1, 1].plot(df.index, df["s"] / 1e3, marker='d', color='purple')  # kJ/kg·K
    axs[1, 1].set_title("Specific Entropy")
    axs[1, 1].set_xlabel("Iteration")
    axs[1, 1].set_ylabel("Entropy (kJ/kg·K)")
    axs[1, 1].grid(True)

    plt.tight_layout()
    plt.show()