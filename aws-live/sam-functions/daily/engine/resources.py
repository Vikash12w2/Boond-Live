from engine.data import get_setting


def gross_depth_mm(net_depth_mm, application_efficiency=None):
    """
    Depth that must be pumped so that net_depth_mm reaches
    the root zone (config irrigation.application_efficiency).
    """
    if application_efficiency is None:
        application_efficiency = get_setting("irrigation", "application_efficiency")

    if application_efficiency <= 0:
        raise ValueError("application_efficiency must be greater than 0")

    return net_depth_mm / application_efficiency


def irrigation_volume_litres(
    depth_mm,
    area_acres
):
    """
    Convert irrigation depth over an area into litres.

    1 mm over 1 acre = 4.0469 m3 (config energy.m3_per_mm_per_acre).
    """

    return irrigation_volume_m3(depth_mm, area_acres) * 1000.0


def irrigation_volume_m3(
    depth_mm,
    area_acres
):
    """
    Convert irrigation depth over an area into cubic metres.
    """

    return depth_mm * area_acres * get_setting("energy", "m3_per_mm_per_acre")


def pump_energy_kwh(
    volume_m3,
    lift_m,
    pump_efficiency
):
    """
    Estimate electrical energy required to pump water.

    Energy = volume * g * lift / (3600 * efficiency)
    """

    if pump_efficiency <= 0:
        raise ValueError("pump_efficiency must be greater than 0")

    gravity = get_setting("energy", "gravity_m_s2")

    return (
        volume_m3
        * gravity
        * lift_m
        / (3600 * pump_efficiency)
    )


def electricity_cost(
    energy_kwh,
    tariff_inr_per_kwh
):
    """
    Estimate electricity cost.

    With the default tariff this is the cost to the power
    system, not the farmer's bill (Punjab farm power is free).
    """

    return energy_kwh * tariff_inr_per_kwh


def co2_emissions(
    energy_kwh,
    grid_factor_kg_per_kwh
):
    """
    Estimate CO2e emissions from electricity consumption.
    """

    return energy_kwh * grid_factor_kg_per_kwh
