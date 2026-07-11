import pytest
from models.thermal_objects import *

def test_fluid_state_copy_is_independent():
    state = FluidState("R134a")
    state.update_from_psat(2e5, quality=1)
    copied = state.copy()

    copied.h += 1e3
    assert state.h != copied.h
    assert state.p == copied.p

def test_compressor_increases_pressure_and_enthalpy():
    state = FluidState("R134a")
    state.m_flow = 0.03
    state.update_from_psat(2e5, quality=1)

    comp = Compressor(p_max=12e5, m_flow_max=0.05, isentropic_efficiency=0.8)
    out = comp.pipe(state)

    assert out.p == 12e5
    assert out.h > state.h
    assert comp.power_consumed > 0

    
def test_expansion_valve_is_isenthalpic():
    state = FluidState("R134a")
    state.update_from_psat(2e5, quality=1)

    valve = ExpansionValve(p_low=1e5)
    out = valve.pipe(state)

    assert out.p == 1e5
    assert out.h == state.h


def test_heat_exchanger_transfers_heat():
    state_in = FluidState("R134a")
    state_in.m_flow = 0.03
    state_in.update_from_psat(2e5, quality=1)

    connected_loop = SecondaryLoop(fluid="Water", m_flow=0.3, t_in=303.15)
    hx = HeatExchanger(area=2.0, k_value=500, connected_loop=connected_loop)

    out = hx.pipe(state_in)

    assert hx.heat_transferred > 0
    assert connected_loop.t_out > connected_loop.t_in

def test_heat_exchanger_limits_enthalpy():
    state_in = FluidState("Water")
    state_in.m_flow = 0.3
    state_in.update_from_psat(1, quality=1)

    connected_loop = SecondaryLoop(fluid="Water", m_flow=0.3, t_in=303.15)
    hx = HeatExchanger(area=2.0, k_value=500, connected_loop=connected_loop)

    out = hx.pipe(state_in)

    # Ensure that the outgoing enthalpy does not exceed the limit set by the connected loop
    target_q = 0.0 if state_in.t > connected_loop.t_in else 1.0
    h_limit = CP.PropsSI('H', 'P', state_in.p, 'Q', target_q, state_in.fluid)
    
    if state_in.t > connected_loop.t_in:
        assert out.h >= h_limit
    else:
        assert out.h <= h_limit

def test_secondary_loop_temperature_update():
    loop = SecondaryLoop(fluid="Water", m_flow=0.3, t_in=303.15)
    initial_t_out = loop.t_out

    # Simulate some heat transfer
    loop.t_out += 5.0  # Increase output temperature by 5 K

    assert loop.t_out == initial_t_out + 5.0

