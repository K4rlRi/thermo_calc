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
    volume_in = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality=1.0, name="in") 
    comp = Compressor(displacement=0.0005, isentropic_efficiency=0.8, name="Compressor")
    volume_out = ChargeVolume(fluid="R134a", volume=0.008, initial_p=2e5, initial_quality = 1.0, name="out") 

    h_out1 = volume_out.h
    p_out1 = volume_out.p
    m_dot_out1 = volume_in.m_flow


    for i in range(2):
        volume_in(volume_out, comp, dt)
        comp(volume_in, volume_out, dt = dt)
        volume_out(comp, volume_in, dt)

        volume_in.integrate(comp, dt)
        volume_out.integrate(volume_in, dt)

    h_out2 = volume_out.h
    p_out2 = volume_out.p
    m_dot_in2 = volume_out.m_dot_in

    print(f"h before, after: {h_out1}, {h_out2}")
    print(f"p before, after: {p_out1}, {p_out2}")
    print(f"m_dot before, after: {m_dot_out1}, {m_dot_in2}")
    
    assert h_out2 > h_out1
    assert p_out2 > p_out1
    assert m_dot_in2 > m_dot_out1


    assert comp.power_consumed > 0

