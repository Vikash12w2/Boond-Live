import pytest

from engine.resources import (
    gross_depth_mm,
    irrigation_volume_litres,
    irrigation_volume_m3,
    pump_energy_kwh,
    electricity_cost,
    co2_emissions
)


def test_resource_chain_for_18_mm_on_one_acre():
    litres = irrigation_volume_litres(18.0, 1.0)
    volume = irrigation_volume_m3(18.0, 1.0)
    energy = pump_energy_kwh(volume, 30.0, 0.40)

    # config energy.m3_per_mm_per_acre = 4.0469
    assert litres == pytest.approx(72844.2)
    assert volume == pytest.approx(72.8442)
    assert energy == pytest.approx(72.8442 * 9.81 * 30.0 / (3600 * 0.40))
    assert electricity_cost(energy, 8.0) == pytest.approx(energy * 8.0)
    assert co2_emissions(energy, 0.70) == pytest.approx(energy * 0.70)


def test_one_mm_one_acre_30_m_lift_40_percent_matches_spec():
    volume = irrigation_volume_m3(1.0, 1.0)

    assert pump_energy_kwh(volume, 30.0, 0.40) == pytest.approx(0.827, abs=1e-3)


def test_zero_efficiency_is_rejected():
    with pytest.raises(ValueError):
        pump_energy_kwh(1.0, 30.0, 0.0)


def test_gross_depth_uses_application_efficiency():
    # config irrigation.application_efficiency = 0.70
    assert gross_depth_mm(70.0) == pytest.approx(100.0)
    assert gross_depth_mm(70.0, application_efficiency=1.0) == 70.0
