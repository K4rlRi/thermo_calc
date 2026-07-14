from models.thermal_objects import *
from solver import *

# 1. Setup Environment & Demands
mass_1 = FluidState("Water")
mass_1.m_flow = 0.5  # 500 grams per second (ground source, evaporator supply)
mass_1.update_from_tp(280, 101325)  # 6.85 °C ground water

mass_2 = FluidState("Water")
mass_2.m_flow = 0.3  # 300 grams per second (floor heating, condenser supply)
mass_2.update_from_tp(303.15, 101325)  # 30 °C return heating flow


# 2. Setup Cycle Components
comp = Compressor(displacement=0.0005, isentropic_efficiency=0.8, name="Compressor")
evap = HeatExchanger(area=2.5, k_value=700, secondary_mass=5.0, boundary_condition=mass_1, name="Evap")
valve = ExpansionValve(flow_coefficient=0.0001, name="MainValve")
cond = HeatExchanger(area=2.0, k_value=500, secondary_mass=5.0, boundary_condition=mass_2, name="Cond")

# 3. Initialize the condenser's and evaporator's own refrigerant charge volumes
# (the compressor/valve meter flow between them but hold no state of their
# own). Starting close to the pressures these should settle near for the given
# secondary temperatures keeps the initial transient mild.
volume_comp_cond = ChargeVolume(fluid="R134a", volume=0.005, initial_p=8e5, initial_quality=0.3, name="Comp-Cond")  # ~31 °C sat.
volume_cond_valve = ChargeVolume(fluid="R134a", volume=0.005, initial_p=8e5, initial_quality=0.3, name="Cond-Valve")  # ~31 °C sat.
volume_valve_evap = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=0.3, name="Valve-Evap")  # ~-10 °C sat.
volume_evap_comp = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=0.3, name="Evap-Comp")  # ~-10 °C sat.


# 4. Simulation Execution. This system is stiff relative to a 0.1 s step (the
# refrigerant volumes are small); dt=0.01 s was confirmed by halving until
# results stopped changing, following the same convergence check Chi & Didion
# used to settle on their own step size.
print("Simulating cycle...")

timestep = 0.01  # seconds
solver = TransientCycleSolver([comp, volume_comp_cond, cond, volume_cond_valve, valve,  volume_valve_evap, evap, volume_evap_comp])

n_steps = 6000  # 60 s
for i in range(n_steps):
    solver.step(dt=timestep, verbose=(i % 100 == 0 or i == n_steps - 1))

# 5. Visualize the transient trajectories
solver.show_history()
