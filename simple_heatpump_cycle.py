from models.thermal_objects import *
from solver.solver import TransientCycleSolver

# 1. Setup Secondary Volumes to and from heat is transfered
mass_1 = FluidState("Water")
mass_1.m_flow = 0.5  
mass_1.update_from_tp(273.15+10, 101325) # source

mass_2 = FluidState("Water")
mass_2.m_flow = 0.5 
mass_2.update_from_tp(273.15+25, 101325)  # sink

refrigerent = "R134a" # define refrigerent type

# 2. Setup Cycle Components
comp = Compressor(displacement=0.0005, isentropic_efficiency=0.8, speed_rpm=4000, name="Compressor")
evap = HeatExchanger(area=2.5, k_value=700, secondary_mass=5.0, boundary_condition=mass_1,  name="Evap")
valve = ExpansionValve(flow_coefficient=0.00005, name="MainValve")
cond = HeatExchanger(area=2.0, k_value=500, secondary_mass=5.0, boundary_condition=mass_2, name="Cond")

# 3. Initialize the charge volumes between every active component
init_p_high = 6e5  # condenser-side starting pressure
init_p_low = 2.5e5  # evaporator-side starting pressure
volume_comp_cond = ChargeVolume(fluid=refrigerent, volume=0.005, initial_p=init_p_high, initial_quality=0.3, name="Comp-Cond")
volume_cond_valve = ChargeVolume(fluid=refrigerent, volume=0.005, initial_p=init_p_high, initial_quality=0.3, name="Cond-Valve")
volume_valve_evap = ChargeVolume(fluid=refrigerent, volume=0.008, initial_p=init_p_low, initial_quality=0.3, name="Valve-Evap")
volume_evap_comp = ChargeVolume(fluid=refrigerent, volume=0.008, initial_p=init_p_low, initial_quality=0.3, name="Evap-Comp")



# 4. Simulation Execution
# putting all components in order
the_cycle = [comp, volume_comp_cond, cond, volume_cond_valve, valve,  volume_valve_evap, evap, volume_evap_comp]
print("Simulating cycle...")
solver = TransientCycleSolver(the_cycle)

n_steps = 10000 # int
timestep = 0.01  # seconds
solver.solve(n_steps=n_steps, dt = timestep)

# get single componetn history df
# df = volume_comp_cond.get_history()
# print(df.head())

# get full cycle history dataframe
df = solver.get_full_history()
print(df.head())

# save full history to .csv
solver.save_full_history()


# 5. Visualize the transient trajectories
solver.show_history()

# visualize single componetn history df
# volume_cond_valve.show_history()