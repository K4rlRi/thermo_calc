# Modular Transient Heatpump simulation
The goal of this simulation is to realistically predict the transient startup behavior of a heatpump converging into steady-state operation. In future versions this tool could be advanced into simulating more complex fluid-heating systems.

## Structure of the project
1. The user creates the fluid cycle by adding together individual blocks: a ChargeVolume must be placed between every "active" property-changing block, acting as an accumulator and change integrator.
2. The list of blocks is then passed through the solver, to iterate through a user-defined number of timesteps with a certain time delta.
3. The simulation results of the whole cycle can then be plotted and saved using methods of the solver.

## Running the Demo simulation
`simple_heatpump_cycle.py` sets up a full cycle (compressor, evaporator, expansion valve, condenser, each separated by a ChargeVolume) against ground-source and floor-heating secondary loops, runs it forward with `TransientCycleSolver`, and plots the resulting pressure/temperature/mass-flow trajectories. 
Example Plot of `solver.show_history()`: 

![Simple Cycle Plot of full cycle](https://github.com/K4rlRi/thermo_calc/blob/dev/demo_simple_cycle/Heatpump_full_cycle_plot.png?raw=true)


## Modelling approach
The Heatpump was modelled using separate object-oriented blocks for each component, making future expansion easier. Each ChargeVolume integrates the two true state variables - mass and internal energy - from the flows crossing its boundary; pressure, temperature and enthalpy are then derived from those via CoolProp. The simulation is advanced by applying the explicit Euler method. Each block saves its own state at every timestep.

## Overview of the model blocks
A full heatpump cycle is wired as a ring: Compressor - ChargeVolume - HeatExchanger (condenser) - ChargeVolume - ExpansionValve - ChargeVolume - HeatExchanger (evaporator) - ChargeVolume - back to Compressor. Each block only ever looks at its immediate neighbours' current state, so the ring can be reordered or extended with more blocks without changing any block's own code. 

### Compressor
Parameters: displacement (m³/rev), isentropic efficiency, speed (rpm).

Meters refrigerant mass flow from one ChargeVolume to another. Over time this builds up a pressure difference between the two, as the mass leaving one and arriving in the other accumulates. The mass flow is the ideal displaced volume (displacement × speed) times the suction density, scaled by a volumetric efficiency that falls off as the pressure ratio grows - so the compressor throttles its own throughput back instead of forcing mass into an already over-pressured high side. The outlet enthalpy is computed from an isentropic compression to the discharge pressure, then corrected by the isentropic efficiency. Power consumed is `m_flow * (h_real - h_in)`. The compressor holds no pressure state of its own - both suction and discharge pressure belong to the neighbouring ChargeVolumes.

### Expansion Valve
Parameters: flow coefficient (kv).

Meters refrigerant from the high-pressure ChargeVolume into the low-pressure one via isenthalpic throttling: outlet enthalpy always equals inlet enthalpy (no work, no heat exchange). Mass flow follows a valve-equation form, `m_flow = kv * sqrt(pressure_drop * density_in)`, with the pressure drop floored to a small positive value so the flow never goes to zero or imaginary when the two sides are near equilibrium.

### Heatexchanger
Parameters: heat transfer area (m²), overall heat transfer coefficient (k_value), secondary fluid mass held up in the exchanger (kg), a boundary condition (a `FluidState` describing the secondary loop's supply temperature/pressure/mass flow), and a connecting-pipe flow coefficient (pipe_kv).

-> `UA = area * k_value`

Exchanges heat between one side of the refrigerant charge (a ChargeVolume) and a dynamically-integrated secondary fluid node defined by a FluidState instance. The secondary side's supply (input) temperature is fixed for the whole simulation. It is assumed to be a single well-mixed zone, not a spatially resolved superheat/condensing/subcooling split. 
While the refrigerant is two-phase its temperature is pinned near saturation (effectively infinite capacity rate), so heat transfer is plain conductance, `UA * (t_secondary - t_refrigerant)` - positive when heat flows into the refrigerant, e.g. in an evaporator. Once the refrigerant is single-phase (superheated vapour or subcooled liquid), its own finite flow capacity limits how much heat it can absorb or reject, handled with effectiveness-NTU against that capacity. The secondary node's own temperature is advanced by an open control-volume energy balance against its upstream reservoir supply.
The heat exchanger's connecting pipe also has a real (if small) flow resistance, which is what actually drives its refrigerant mass flow.

#### FluidState
A class that collects all parameters of a current fluid state. Initially it is set using a plain fluid name, like "water". The name must be compatible with the CoolProp library. With a combination of two parameters, the current state can then be set using one of the `update` methods.


### Chargevolume
Parameters: fluid, volume (m³), initial pressure, initial vapor quality.

Represents a fixed-volume refrigerant accumulator - e.g. a compressor manifold plus condenser, or an expansion valve plus evaporator. This is what connects the cycle's high/low pressure to the refrigerant's real thermal state. Total mass and internal energy are the two state variables integrated from the flows crossing the volume's boundary (bounded to a maximum fractional change per step for numerical stability); pressure, temperature and enthalpy are *derived* from density (m/V) and specific internal energy (U/m) via the CoolProp library. A ChargeVolume never meters or restricts flow itself - it only records what arrives and passes the same rate on as its own `m_dot_out` for whichever block reads it next.


## Solver
Every block implements `__call__(in_charge, out_charge, dt)`; the metering components (Compressor, ExpansionValve, HeatExchanger) set their own `m_flow` and `h`, while ChargeVolume instead integrates its mass/energy balance from the in/out flows once every block's output for the step is known. 

The step is a single sequential pass in list order, so every block's own
ChargeVolume neighbours' state (p/h/t) is always current, and every
ChargeVolume exposes the flow it just received as its own `m_dot_out` for
whichever edge comes next to read. But one connection in the
ring is unavoidably one step stale: the compressor's suction neighbour is
processed last in the pass.

## Tests
Unit tests for the individual blocks live in `test/test_thermal_objects.py` and can be run with:

```bash
pytest
```

## Sources
- The state of refrigerant and secondary heat source fluids is calculated using the CoolProp Library.

The approach follows
- J. Chi, D. Didion, A simulation model of the transient performance of a heat pump, International Journal of Refrigeration, Volume 5, Issue 3, 1982



This project was done in the context of the [Software and Computing for Applied Physics Course](https://unibodifabiophysics.github.io/programmingCourseDIFA/) at the University of Bologna. 

Summer Term 2026