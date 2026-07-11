# from support.tracking import *

import matplotlib.pyplot as plt
import pandas as pd

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