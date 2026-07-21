import matplotlib.pyplot as plt
import pandas as pd

def plot_cycle_history(df: pd.DataFrame, title: str = "Heat Pump Cycle"):
    """Plot the transient trajectories of a TransientCycleSolver run: refrigerant
    and secondary-loop temperatures, refrigerant pressures, and mass flows vs time. """
    if df.empty:
        print(f"No history data available to plot for {title}.")
        return

    p_cols = [c for c in df.columns if c.endswith("_p")]
    t_secondary_in_cols = [c for c in df.columns if c.endswith("_t_secondary_in")]
    t_secondary_out_cols = [c for c in df.columns if c.endswith("_t_secondary_out")]
    t_cols = [c for c in df.columns if c.endswith("_t")]
    m_flow_cols = [c for c in df.columns if c.endswith("_mdot")]
    qdot_cols = [c for c in df.columns if c.endswith("_qdot")]

    fig, axs = plt.subplots(4, 1, figsize=(10, 13), sharex=True)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # 1. Pressures
    for c in p_cols:
        axs[0].plot(df.index, df[c] / 1e5, label=c.removesuffix("_p"))
    axs[0].set_ylabel("Pressure (bar)")
    axs[0].set_title("Refrigerant pressure")
    axs[0].legend()
    axs[0].grid(True)

    # 2. Temperatures: refrigerant (solid) vs secondary loop supply/return (dotted/dashed)
    for c in t_cols:
        axs[1].plot(df.index, df[c] - 273.15, label=c.removesuffix("_t"))
    for c in t_secondary_in_cols:
        axs[1].plot(df.index, df[c] - 273.15, linestyle=':',
                    label=c.removesuffix("_t_secondary_in") + " (secondary in)")
    for c in t_secondary_out_cols:
        axs[1].plot(df.index, df[c] - 273.15, linestyle='--',
                    label=c.removesuffix("_t_secondary_out") + " (secondary out)")
    axs[1].set_ylabel("Temperature (°C)")
    axs[1].set_title("Refrigerant vs secondary loop temperature")
    axs[1].legend()
    axs[1].grid(True)

    # 3. Mass flows
    for c in m_flow_cols:
        axs[2].plot(df.index, df[c], label=c.removesuffix("_mdot"))
    axs[2].set_ylabel("Mass flow (kg/s)")
    axs[2].set_title("Refrigerant mass flow")
    axs[2].legend()
    axs[2].grid(True)

    # 4. Heat exchanger duty (Qdot), positive = heat flows into the refrigerant
    for c in qdot_cols:
        axs[3].plot(df.index, df[c], label=c.removesuffix("_qdot"))
    axs[3].axhline(0, color='gray', linewidth=0.8)
    axs[3].set_ylabel("Qdot (W)")
    axs[3].set_xlabel("Time (s)")
    axs[3].set_title("Heat exchanger duty")
    axs[3].legend()
    axs[3].grid(True)

    plt.tight_layout()
    plt.show()

def plot_component_history(df: pd.DataFrame, title: str):
    """Plot every state variable a single component tracked over its own
    history, one subplot per column.
    """
    if df.empty:
        print(f"No history data available to plot for {title}.")
        return

    cols = list(df.columns)
    n_cols = 2
    n_rows = -(-len(cols) // n_cols)  # ceil division

    fig, axs = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows), squeeze=False)
    fig.suptitle(f"Convergence History: {title}", fontsize=16, fontweight='bold')

    for i, col in enumerate(cols):
        ax = axs[i // n_cols][i % n_cols]
        label = col.removeprefix(f"{title}_")

        values = df[col]
        if label == "p":
            values, ylabel = values / 1e5, "Pressure (bar)"
        elif label in ("t", "t_secondary_in", "t_secondary_out"):
            values, ylabel = values - 273.15, "Temperature (°C)"
        elif label == "h":
            values, ylabel = values / 1e3, "Enthalpy (kJ/kg)"
        elif label == "mdot":
            ylabel = "Mass flow (kg/s)"
        elif label == "qdot":
            ylabel = "Qdot (W)"
        elif label == "power_consumed":
            ylabel = "Power (W)"
        elif label == "speed_rpm":
            ylabel = "Speed (rpm)"
        else:
            ylabel = label

        ax.plot(df.index, values, marker='.')
        ax.set_title(label)
        ax.set_xlabel(df.index.name or "Iteration")
        ax.set_ylabel(ylabel)
        ax.grid(True)

    for j in range(len(cols), n_rows * n_cols):
        axs[j // n_cols][j % n_cols].axis('off')  # Blank out any leftover grid cells (e.g. an odd number of tracked columns)

    plt.tight_layout()
    plt.show()