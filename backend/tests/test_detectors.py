"""Unit tests for the live detector logic (trackers, fingerprinting, Apex).

The trackers are pure logic — they return event dicts, they don't capture or
write to the DB — so they're tested directly with synthetic input, no Wi-Fi
hardware. Scapy is used only to build in-memory beacons for the fingerprint
and security parsers.
"""
from scapy.all import Dot11, Dot11Beacon, Dot11Elt  # type: ignore

from detectors import live_capture as L
from detectors.responder import ApexResponder


# --- deauth/disassoc burst ---------------------------------------------
def test_burst_fires_at_threshold():
    t = L.BurstTracker("deauth_burst", "deauth")
    for _ in range(L.BURST_THRESHOLD):
        t.add("aa:bb:cc:00:00:01", "ff:ff:ff:ff:ff:ff", 7)
    ev = t.maybe_emit(6)
    assert ev is not None
    assert ev["event_type"] == "deauth_burst"
    assert ev["channel"] == 6


def test_burst_below_threshold_silent():
    t = L.BurstTracker("deauth_burst", "deauth")
    for _ in range(L.BURST_THRESHOLD - 1):
        t.add("aa:bb:cc:00:00:01", "ff:ff:ff:ff:ff:ff", 7)
    assert t.maybe_emit(6) is None


# --- beacon / SSID flood -----------------------------------------------
def test_beacon_flood_on_many_ssids_one_bssid():
    t = L.BeaconFloodTracker()
    ev = None
    for i in range(L.BeaconFloodTracker.SSIDS_PER_BSSID):
        ev = t.add("de:ad:be:ef:00:01", f"FakeNet{i}")
    assert ev is not None and ev["event_type"] == "beacon_flood"


def test_beacon_flood_quiet_under_threshold():
    t = L.BeaconFloodTracker()
    last = None
    for i in range(L.BeaconFloodTracker.SSIDS_PER_BSSID - 1):
        last = t.add("de:ad:be:ef:00:01", f"FakeNet{i}")
    assert last is None


# --- karma / PineAP ----------------------------------------------------
def test_karma_on_many_ssids():
    t = L.KarmaTracker()
    ev = None
    for i in range(L.KarmaTracker.SSIDS_THRESHOLD):
        ev = t.add("ca:fe:00:00:00:01", f"ProbeNet{i}")
    assert ev is not None and ev["event_type"] == "karma_suspected"


# --- handshake harvest (EAPOL) -----------------------------------------
def test_handshake_harvest_on_eapol_spike():
    t = L.HandshakeHarvestTracker()
    ev = None
    for _ in range(L.HandshakeHarvestTracker.EAPOL_THRESHOLD):
        ev = t.add_eapol()
    assert ev is not None and ev["event_type"] == "handshake_harvest_pattern"


def test_handshake_post_deauth_is_high():
    import time
    t = L.HandshakeHarvestTracker()
    t.recent_deauth = time.time()        # a deauth burst just happened
    ev = None
    for _ in range(L.HandshakeHarvestTracker.EAPOL_THRESHOLD):
        ev = t.add_eapol()
    assert ev["severity"] == "high"
    assert ev["raw_json"]["post_deauth"] is True


# --- evil twin / rogue AP ----------------------------------------------
TRUSTED = [{"ssid": "Home", "bssids": ["AA:BB:CC:00:00:01"],
            "expected_security": "WPA2"}]


def test_rogue_new_bssid():
    t = L.EvilTwinTracker(TRUSTED)
    ev = t.add("Home", "DE:AD:BE:EF:00:09", 6, "WPA2", "fp")
    assert ev["event_type"] == "new_bssid_for_known_ssid"


def test_evil_twin_on_security_downgrade():
    t = L.EvilTwinTracker(TRUSTED)
    ev = t.add("Home", "DE:AD:BE:EF:00:09", 6, "OPEN", "fp")
    assert ev["event_type"] == "evil_twin_suspected"
    assert ev["severity"] == "high"


def test_fingerprint_spoof_on_trusted_bssid():
    import time
    t = L.EvilTwinTracker(TRUSTED)
    bssid = "AA:BB:CC:00:00:01"
    for _ in range(L.EvilTwinTracker.LEARN_HITS):     # learn the legit fp
        t.add("Home", bssid, 6, "WPA2", "goodfp")
    assert "goodfp" in t.good_fps[bssid]
    t.first_seen[bssid] = time.time() - t.LEARN_WINDOW - 1   # close learning
    assert t.add("Home", bssid, 6, "WPA2", "goodfp") is None  # legit fp still ok
    ev = None
    for _ in range(L.EvilTwinTracker.RECUR):          # a new fp must persist
        ev = t.add("Home", bssid, 6, "WPA2", "badfp")
    assert ev is not None
    assert ev["event_type"] == "evil_twin_suspected"
    assert ev["raw_json"]["detector"] == "fingerprint"


def test_multiple_legit_fingerprints_no_false_positive():
    """A multi-radio router with two legit fingerprints must not false-alarm."""
    import time
    t = L.EvilTwinTracker(TRUSTED)
    bssid = "AA:BB:CC:00:00:01"
    for fp in ("fpA", "fpB"):                          # learn both legit variants
        for _ in range(L.EvilTwinTracker.LEARN_HITS):
            t.add("Home", bssid, 6, "WPA2", fp)
    t.first_seen[bssid] = time.time() - t.LEARN_WINDOW - 1
    fired = [t.add("Home", bssid, 6, "WPA2", fp)
             for fp in ("fpA", "fpB") for _ in range(20)]
    assert all(e is None for e in fired)               # both known -> no alert


# --- beacon parsing (scapy) --------------------------------------------
def _beacon(ssid=b"Net", rates=b"\x82\x84\x8b\x96", cap=0x1104,
            rsn=None, vendor=None):
    p = (Dot11(addr2="aa:bb:cc:dd:ee:ff") / Dot11Beacon(cap=cap)
         / Dot11Elt(ID=0, info=ssid) / Dot11Elt(ID=1, info=rates))
    if rsn is not None:
        p = p / Dot11Elt(ID=48, info=rsn)
    if vendor is not None:
        p = p / Dot11Elt(ID=221, info=vendor)
    return p


def test_fingerprint_ignores_volatile_capability():
    fp_a = L.beacon_fingerprint(_beacon(cap=0x1104))
    fp_b = L.beacon_fingerprint(_beacon(cap=0x0104))   # cap differs only
    assert fp_a == fp_b                                 # cap is excluded


def test_fingerprint_changes_on_rates():
    fp_a = L.beacon_fingerprint(_beacon(rates=b"\x82\x84\x8b\x96"))
    fp_b = L.beacon_fingerprint(_beacon(rates=b"\x82\x84"))
    assert fp_a != fp_b


def test_beacon_security_open_vs_wpa2():
    assert L.beacon_security(_beacon(cap=0x0004)) == "OPEN"     # no privacy
    assert L.beacon_security(_beacon(cap=0x1104, rsn=b"\x01\x00")) == "WPA2"


# --- Apex responder (gated active defense) -----------------------------
def _deauth_event(bssid="DE:AD:BE:EF:00:09", sev="high", frames=900):
    return L.events.make_event(
        mode="sentinel", event_type="deauth_burst", confidence=95,
        severity=sev, message="x", bssid=bssid, channel=6,
        raw_json={"frame_count": frames})


def test_apex_disarmed_does_nothing(temp_db):
    r = ApexResponder()
    r.cfg = {"lab_mode": False, "apex_active_response": False}
    assert r.on_deauth(_deauth_event()) is None


def test_apex_protects_own_gear(temp_db):
    r = ApexResponder()
    r.cfg = {"lab_mode": True, "apex_active_response": True,
             "protect_bssids": ["DE:AD:BE:EF:00:09"], "responses": {}}
    assert r.on_deauth(_deauth_event(bssid="DE:AD:BE:EF:00:09")) is None


def test_apex_ignores_insignificant_burst(temp_db):
    r = ApexResponder()
    r.cfg = {"lab_mode": True, "apex_active_response": True,
             "protect_bssids": [], "responses": {}, "min_response_frames": 100}
    assert r.on_deauth(_deauth_event(sev="low", frames=8)) is None


def test_apex_fires_on_real_attack(temp_db):
    r = ApexResponder()
    r.cfg = {"lab_mode": True, "apex_active_response": True,
             "protect_bssids": [], "responses": {"contain": True}}
    ev = r.on_deauth(_deauth_event(bssid="BA:DA:55:00:00:01"))
    assert ev is not None and ev["event_type"] == "apex_response"
    assert ev["target"] == "BA:DA:55:00:00:01"
    # it logged an action to the DB
    assert temp_db.connect().execute(
        "SELECT COUNT(*) FROM actions WHERE action='apex_response'"
    ).fetchone()[0] == 1
