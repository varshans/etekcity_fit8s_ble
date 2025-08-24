import binascii
from src.etekcity_fit8s_ble.adv_reader import _parse_mfr_06d0
from src.etekcity_fit8s_ble.const import WEIGHT_KEY, IMPEDANCE_KEY

def test_parse_mfr_examples():
    # With impedance
    hexstr = "01ffeeddccbbaac0a801d001012c010101020300"
    payload = binascii.unhexlify(hexstr)
    info = _parse_mfr_06d0(payload)
    assert info[WEIGHT_KEY] == 66.0
    assert info[IMPEDANCE_KEY] == 300

    # No impedance (0x0000)
    hexstr2 = "01ffeeddccbbaac0a8012f000000000101020300"
    info2 = _parse_mfr_06d0(binascii.unhexlify(hexstr2))
    assert info2[WEIGHT_KEY] == 0.047
    assert info2[IMPEDANCE_KEY] is None
