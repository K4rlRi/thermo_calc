import pytest
from models.thermal_objects import *

# def test_fluid_state_copy_is_independent():
#     state = FluidState("R134a")
#     state.update_from_psat(2e5, quality=1)
#     copied = state.copy()

#     copied.h += 1e3
#     assert state.h != copied.h
#     assert state.p == copied.p


def test_compressor_increases_pressure_and_enthalpy():
    dt = 0.01
    # Two Volumes with same starting pressure, connected to each other and a compressor
    volume_in = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=1.0, name="in") 
    comp = Compressor(displacement=0.0005, isentropic_efficiency=0.8, name="Compressor")
    volume_out = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality = 1.0, name="out") 

    h_out1 = volume_out.h
    p_out1 = volume_out.p
    m_dot_out1 = volume_in.m_dot_out


    for i in range(5):
        volume_in(volume_out, comp, dt)
        comp(volume_in, volume_out, dt = dt)
        volume_out(comp, volume_in, dt)

        volume_in.integrate(comp, dt)
        volume_out.integrate(volume_in, dt)

    h_out2 = volume_out.h
    p_out2 = volume_out.p
    m_dot_in2 = volume_out.m_dot_in

    # the compressor creates a pressure delta between the two, in the beginning equal pressure, reservoirs
    # creating the p difference uses power and increases the enthalpy
    print(f"h before, after: {h_out1}, {h_out2}")
    print(f"p before, after: {p_out1}, {p_out2}")
    print(f"m_dot before, after: {m_dot_out1}, {m_dot_in2}")
    
    assert h_out2 > h_out1
    assert p_out2 > p_out1
    assert m_dot_in2 > m_dot_out1
    assert comp.power_consumed > 0


def test_expansion_valve_decreases_pressure_and_conserves_enthalpy():
    dt = 0.01
    # High-pressure subcooled liquid feeding the valve (e.g. condenser outlet)
    volume_in = ChargeVolume(fluid="R134a", volume=0.008, initial_p=8e5, initial_quality=0.0, name="in")
    valve = ExpansionValve(flow_coefficient=1e-6, name="ExpansionValve")
    # Low-pressure two-phase mixture downstream of the valve
    volume_out = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=0.3, name="out")

    p_in1 = volume_in.p
    p_out1 = volume_out.p

    for i in range(5):
        volume_in(volume_out, valve, dt)
        valve(volume_in, volume_out, dt=dt)
        # Isenthalpic throttling: tno work and no heat exchange, enthalpy leaving = enthalpy that arrived
        assert valve.h == volume_in.h
        volume_out(valve, volume_in, dt)

        volume_in.integrate(valve, dt)
        volume_out.integrate(volume_in, dt)

    p_in2 = volume_in.p
    p_out2 = volume_out.p

    print(f"p_in before, after: {p_in1}, {p_in2}")
    print(f"p_out before, after: {p_out1}, {p_out2}")
    print(f"valve m_flow: {valve.m_flow}")

    assert p_out1 < p_in1
    # Mass/energy leaves the high p side and arrives at the low p side, so the pressure gap across the valve narrows over time.
    assert (p_in2 - p_out2) < (p_in1 - p_out1)
    assert valve.m_flow > 0

def test_heatexchanger_transfers_heat_into_refrigerent_cycle():
    dt = 0.01

    thermal_source = FluidState("Water")
    thermal_source.m_flow = 0.5  # 500 grams per second (ground source, evaporator supply)
    thermal_source.update_from_tp(280, 101325)  # 6.85 °C ground water
    # High-pressure subcooled liquid feeding the valve (e.g. condenser outlet)
    volume_in = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=0.5, name="in")
    exchanger = HeatExchanger(area=0.1, k_value = 400, secondary_mass = 5.0, boundary_condition= thermal_source, name="Heatexchanger")
    # Low-pressure two-phase mixture downstream of the valve
    volume_out = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=0.5, name="out")

    p_in1 = volume_in.p
    p_out1 = volume_out.p
    h_in1 = volume_in.h
    h_out1 = volume_out.h

    for i in range(2):
        volume_in(volume_out, exchanger, dt)
        exchanger(volume_in, volume_out, dt)
        assert exchanger.h  > volume_in.h
        volume_out(exchanger, volume_in, dt)

        volume_in.integrate(exchanger, dt)
        volume_out.integrate(volume_in, dt)

    p_in2 = volume_in.p
    p_out2 = volume_out.p
    h_in2 = volume_in.h
    h_out2 = volume_out.h

    print(f"p_in before, after: {p_in1}, {p_in2}")
    print(f"p_out before, after: {p_out1}, {p_out2}")
    print(f"valve m_flow: {exchanger.m_flow}")
    print(f"h before, after: {h_out1} , {h_out2}")

    assert p_out1 == p_in1
    # No compressor is driving flow in this isolated test, so the pressure gap
    # should stay essentially unchanged (small drift from the tiny floor flow
    # HeatExchanger uses internally, see thermal_objects.py:233).
    assert (p_in2 - p_out2) == pytest.approx(p_in1 - p_out1, abs=1.0)
    assert h_out2 > h_out1
    # HeatExchanger floors refrigerant flow to 1e-6 kg/s rather than allowing
    # exactly zero (thermal_objects.py:233), so that's the value pinned here.
    assert exchanger.m_flow == pytest.approx(0, abs=1e-5)
    
