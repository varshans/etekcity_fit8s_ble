from src.etekcity_fit8s_ble.adv_reader import AdvReading
from src.etekcity_fit8s_ble.body_metrics import EtekcitySmartFitnessScaleWithBodyMetrics
from src.etekcity_fit8s_ble.const import WEIGHT_KEY, IMPEDANCE_KEY
from src.etekcity_fit8s_ble.parser import (
    WeightUnit,
)

def test_scale_data_from_adv_builds_measurements():
    ar = AdvReading(
        address="AA:BB:CC:DD:EE:FF",
        mac_in_frame="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        weight_kg=70.123,
        impedance_ohm=500,
        stable=True,
        ts=0.0,
        raw_hex="aaaaaaaaaaaaaaa",
    )
    sd = EtekcitySmartFitnessScaleWithBodyMetrics._scale_data_from_adv(ar, WeightUnit.KG)
    assert sd.measurements[WEIGHT_KEY] == 70.123
    assert sd.measurements[IMPEDANCE_KEY] == 500
    assert sd.display_unit == WeightUnit.KG
