from kuma_core.mitigation import MitigationEngine


def _eng():
    return MitigationEngine(cfg={})


def test_canonical_for_deauth_family():
    e = _eng()
    for et in ("deauth_burst", "disassoc_flood", "handshake_harvest", "eapol_burst"):
        assert e.canonical_for(et) == "harden+redirect"


def test_canonical_for_rogue_family():
    e = _eng()
    for et in ("rogue_ap", "new_bssid_for_known_ssid", "evil_twin", "pineapple_karma", "karma_probe"):
        assert e.canonical_for(et) == "contain"


def test_canonical_for_flood_family():
    e = _eng()
    for et in ("beacon_flood", "ssid_flood", "botnet_beacon", "worm_spread"):
        assert e.canonical_for(et) == "mark+contain"


def test_canonical_for_passive_fallback():
    e = _eng()
    assert e.canonical_for("sniffer_detected") == "mark"
    assert e.canonical_for("rf_jam") == "mark"
    assert e.canonical_for("") == "mark"
