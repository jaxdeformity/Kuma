"""Tests for the CSA (Channel Switch Announcement) attack detector."""
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap  # type: ignore

from detectors.csa_detector import CsaTracker, parse_csa


def _beacon(ssid: str, bssid: str, new_ch: int, count: int = 0, mode: int = 1):
    """A beacon carrying a CSA element (tag 37: mode, new_channel, switch_count)."""
    csa = Dot11Elt(ID=37, info=bytes([mode, new_ch, count]))
    return (RadioTap()
            / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid)
            / Dot11Beacon(cap="ESS")
            / Dot11Elt(ID=0, info=ssid.encode())
            / csa)


def test_parse_csa_extracts_ie():
    pkt = _beacon("Net", "AA:BB:CC:DD:EE:FF", new_ch=6, count=3, mode=0)
    assert parse_csa(pkt) == (6, 3, 0)        # (new_channel, switch_count, switch_mode)


def test_parse_csa_none_when_absent():
    pkt = (RadioTap() / Dot11(addr2="AA:BB:CC:DD:EE:FF")
           / Dot11Beacon() / Dot11Elt(ID=0, info=b"Net"))
    assert parse_csa(pkt) is None


def test_invalid_channel_flagged():
    t = CsaTracker(trusted=[])
    ev = t.add("AA:BB:CC:DD:EE:FF", "RandomAP", cur_channel=6,
               new_ch=0, switch_count=0, switch_mode=1)   # channel 0 = bogus
    assert ev is not None
    assert ev["event_type"] == "csa_attack" and ev["severity"] == "high"
    assert "INVALID channel" in ev["message"]


def test_forged_csa_against_trusted_ssid_flagged():
    t = CsaTracker(trusted=[{"ssid": "HomeLab"}])
    ev = t.add("AA:BB:CC:DD:EE:FF", "HomeLab", cur_channel=6,
               new_ch=11, switch_count=2, switch_mode=0)   # valid ch, but trusted SSID
    assert ev is not None
    assert "spoofing trusted SSID 'HomeLab'" in ev["message"]
    assert ev["confidence"] >= 90


def test_csa_storm_flagged():
    t = CsaTracker(trusted=[], window=12.0, storm=4)
    last = None
    for _ in range(4):                          # 4 CSA to valid, non-trusted -> storm
        last = t.add("11:22:33:44:55:66", "OpenAP", cur_channel=6,
                     new_ch=11, switch_count=3, switch_mode=0)
    assert last is not None
    assert "CSA storm" in last["message"]


def test_single_legit_csa_not_flagged():
    # one CSA, valid channel, non-trusted SSID, gentle switch -> plausibly legit, no alert
    t = CsaTracker(trusted=[])
    ev = t.add("11:22:33:44:55:66", "OpenAP", cur_channel=6,
               new_ch=11, switch_count=5, switch_mode=0)
    assert ev is None
