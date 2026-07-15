# Mudular Transient Heatpump simulation
The Heatpump was modelled using separate blocks for each component, making future expansion easier. Each component calculates the derivative of the two coordinate properties h and mass flow. The simulation is done applying the explicit Eulers method. 

## Overview of the model blocks
The assumptions and applied physics are described here. A full cycle is wired as a ring: Compressor - ChargeVolume - HeatExchanger (condenser) - ChargeVolume - ExpansionValve - ChargeVolume - HeatExchanger (evaporator) - ChargeVolume - back to Compressor. Each block only ever looks at its immediate neighbours' current state, so the ring can be reordered or extended with more blocks without changing any block's own code.

### Compressor
Parameters: displacement (m³/rev), isentropic efficiency, speed (rpm).

Meters refrigerant mass flow from the low-pressure ChargeVolume into the high-pressure one. Mass flow is the ideal displaced volume (displacement × speed) times the suction density, scaled by a volumetric efficiency that falls off as the pressure ratio grows - so the compressor throttles its own throughput back instead of forcing mass into an already over-pressured high side. The outlet enthalpy is computed from an isentropic compression to the discharge pressure, then corrected by the isentropic efficiency. Power consumed is `m_flow * (h_real - h_in)`. The compressor holds no pressure state of its own - both suction and discharge pressure belong to the neighbouring ChargeVolumes.

### Expansion Valve
Parameters: flow coefficient (kv).

Meters refrigerant from the high-pressure ChargeVolume into the low-pressure one via isenthalpic throttling: outlet enthalpy always equals inlet enthalpy (no work, no heat exchange). Mass flow follows a valve-equation form, `m_flow = kv * sqrt(pressure_drop * density_in)`, with the pressure drop floored to a small positive value so the flow never goes to zero or imaginary when the two sides are near equilibrium.

### Heatexchanger
Parameters: heat transfer area, overall heat transfer coefficient (k_value), secondary fluid mass held up in the exchanger, and a boundary condition (a `FluidState` describing the secondary loop's supply temperature/pressure/mass flow).

Exchanges heat between one side of the refrigerant charge (a ChargeVolume) and a lumped, dynamically-integrated secondary fluid node - a single well-mixed zone, not a spatially resolved superheat/condensing/subcooling split. Following Chi & Didion (1982): while the refrigerant is two-phase its temperature is pinned near saturation (effectively infinite capacity rate), so heat transfer is plain conductance, `UA * (t_refrigerant - t_secondary)`. Once the refrigerant is single-phase (superheated vapour or subcooled liquid), its own finite flow capacity limits how much heat it can absorb or reject, handled with effectiveness-NTU against that capacity. The secondary node's own temperature is advanced by an open control-volume energy balance against its upstream reservoir supply.

### Chargevolume
Parameters: fluid, volume (m³), initial pressure, initial vapor quality.

Represents a fixed-volume refrigerant accumulator - e.g. a compressor manifold plus condenser, or an expansion valve plus evaporator, lumped together as one "side" of the cycle. This is what pins the cycle's high/low pressure to the refrigerant's real thermal state: total mass and internal energy are integrated from the flows crossing the volume's boundary (bounded to a maximum fractional change per step for numerical stability), and pressure/temperature/enthalpy are *derived* from density (m/V) and specific internal energy (U/m) via CoolProp, rather than pushed along an independent ideal-gas guess. A ChargeVolume never meters or restricts flow itself - it only records what arrives and passes the same rate on as its own `m_flow` for whichever block reads it next; only the Compressor and ExpansionValve actually meter flow.

## Running the simulation
`simple_heatpump_cycle.py` wires up a full cycle (compressor, evaporator, expansion valve, condenser, each separated by a ChargeVolume) against ground-source and floor-heating secondary loops, runs it forward with `TransientCycleSolver`, and plots the resulting pressure/temperature/mass-flow trajectories:

```bash
python simple_heatpump_cycle.py
```

Unit tests for the individual blocks live in `test/test_thermal_objects.py` and can be run with:

```bash
pytest
```

## Sources
The approach follows
- J. Chi, D. Didion, A simulation model of the transient performance of a heat pump, International Journal of Refrigeration, Volume 5, Issue 3, 1982



This project was done in the context of the [Software and Computing for Applied Physics Course](https://unibodifabiophysics.github.io/programmingCourseDIFA/) at the University of Bologna. 

Summer Term 2026