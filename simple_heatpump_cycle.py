from models.thermal_objects import *

# 1. Setup Environment & Demands
ground_source = SecondaryLoop(fluid="Water", m_flow=0.5, t_in=283.15)  # 10 °C ground water
floor_heating = SecondaryLoop(fluid="Water", m_flow=0.3, t_in=303.15)  # 30 °C return heating flow

# 2. Setup Cycle Components
# Let's use R134a, evaporating at 2 bar (~ -10°C) and condensing at 12 bar (~ +46°C)
comp = Compressor(p_max=12e5, m_flow_max=0.05)
cond = HeatExchanger(area=2.0, k_value=500, connected_loop=floor_heating)
valve = ExpansionValve(p_low=2e5)
evap = HeatExchanger(area=2.5, k_value=400, connected_loop=ground_source)

# 3. Initialize the Fluid
refrigerant = FluidState("R134a")
refrigerant.m_flow = 0.03  # 30 grams per second
refrigerant.update_from_psat(2e5, quality=1)  # Start as saturated gas at low pressure

# 4. Simulation Execution (The Chain)
print("Simulating cycle...")
state_1 = refrigerant

for iteration in range(10): # In a real solver, you loop until state_1 stops changing
    state_2 = comp.pipe(state_1)
    state_3 = cond.pipe(state_2)
    state_4 = valve.pipe(state_3)
    state_1 = evap.pipe(state_4) # Feeds back into compressor next iteration

# 5. Calculate Efficiency (COP)
cop = cond.heat_transferred / comp.power_consumed

print(f"--- Results ---")
print(f"Compressor Power: {comp.power_consumed:.2f} W")
print(f"Heating Power Delivered: {cond.heat_transferred:.2f} W")
print(f"Heat Pump COP: {cop:.2f}")
print(f"Heating Water Output Temp: {floor_heating.t_out - 273.15:.2f} °C")

evap.show_history()
comp.show_history()