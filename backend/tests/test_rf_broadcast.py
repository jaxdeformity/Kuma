"""Unit tests for Tier B broadcast offense (no radio/real-time; all injected)."""
from kuma_core.authz import Gate
from offense.rf_broadcast import BroadcastRF, BroadcastResult


def _bcast_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
           "broadcast": {"channel": 6, "max_tx_power_dbm": 5,
                         "max_burst_seconds": 3, "honor_protect_bssids": True}}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


class _Clock:
    """Deterministic monotonic clock: each call advances by `step` seconds."""
    def __init__(self, step=1.0):
        self.t = 0.0
        self.step = step

    def __call__(self):
        v = self.t
        self.t += self.step
        return v


# ---------------------------------------------------------------------------
# Task 1: time-box core + duration cap
# ---------------------------------------------------------------------------

def test_run_burst_is_time_boxed(tmp_path):
    g = _bcast_gate(tmp_path)
    rf = BroadcastRF(gate=g, clock=_Clock(step=1.0), sleep=lambda *_: None)
    n = []
    bursts = rf._run_burst(lambda: n.append(1), duration=3)
    # clock advances 1.0/call: elapsed 0,1,2 < 3 -> 3 sends, then 3 not < 3 -> stop
    assert bursts == 3
    assert len(n) == 3


def test_cap_duration_to_max_burst_seconds(tmp_path):
    g = _bcast_gate(tmp_path)   # max_burst_seconds = 3
    rf = BroadcastRF(gate=g)
    assert rf._cap_duration(999) == 3
    assert rf._cap_duration(2) == 2
    assert rf._cap_duration(None) == 3       # default to the cap


# FIX C1: validate cap
def test_cap_duration_rejects_invalid_max_burst(tmp_path):
    import pytest
    # max_burst_seconds = 0 must raise
    cfg_zero = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
                "broadcast": {"channel": 6, "max_tx_power_dbm": 5,
                               "max_burst_seconds": 0, "honor_protect_bssids": True}}
    g_zero = Gate(config=cfg_zero, audit_file=tmp_path / "audit_zero.jsonl")
    rf_zero = BroadcastRF(gate=g_zero)
    with pytest.raises(ValueError, match="invalid max_burst_seconds"):
        rf_zero._cap_duration(5)

    # max_burst_seconds = None must raise
    cfg_none = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
                "broadcast": {"channel": 6, "max_tx_power_dbm": 5,
                               "max_burst_seconds": None, "honor_protect_bssids": True}}
    g_none = Gate(config=cfg_none, audit_file=tmp_path / "audit_none.jsonl")
    rf_none = BroadcastRF(gate=g_none)
    with pytest.raises(ValueError, match="invalid max_burst_seconds"):
        rf_none._cap_duration(5)


# ---------------------------------------------------------------------------
# Task 2: deauth_flood
# ---------------------------------------------------------------------------

def test_deauth_flood_denied_when_not_broadcast_armed(tmp_path):
    g = _bcast_gate(tmp_path, broadcast_armed=False)   # one arm missing
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=3)
    assert res.ok is False
    assert "broadcast_armed off" in res.reason
    assert sent == []                                   # never transmitted


def test_deauth_flood_armed_transmits_timeboxed(tmp_path):
    g = _bcast_gate(tmp_path)                            # max_burst_seconds=3
    sent, chans = [], []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(len(frames)),
                     set_channel=lambda iface, ch: chans.append(ch),
                     clock=_Clock(step=1.0), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=999)                 # asks for huge; capped to 3
    assert res.ok is True
    assert res.seconds == 3                              # capped
    assert chans == [6]                                  # pinned channel tuned once
    assert len(sent) == 3                                # 3 bursts (clock-driven)


def test_deauth_flood_excludes_protected_bssids(tmp_path):
    g = _bcast_gate(tmp_path, protect_bssids=["aa:bb:cc:dd:ee:ff"])
    targets_seen = []

    def cap_sender(frames, iface, count):
        # record the bssid (addr2) of the first frame each burst
        from scapy.all import Dot11  # type: ignore
        targets_seen.append(frames[0][Dot11].addr2.upper())

    rf = BroadcastRF(gate=g, sender=cap_sender, set_channel=lambda *a: None,
                     clock=_Clock(step=3.0), sleep=lambda *_: None)  # 1 burst then stop
    res = rf.deauth_flood(duration=3,
                          bssids=["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
    assert res.ok is True
    assert "AA:BB:CC:DD:EE:FF" not in targets_seen      # protected one excluded
    assert "11:22:33:44:55:66" in targets_seen


def test_deauth_flood_dry_run(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None,
                     dry_run=True)
    res = rf.deauth_flood(duration=3)
    assert res.ok is True and res.dry_run is True
    assert res.bursts == 0
    assert sent == []


# FIX C2: channel pin fail-closed — deauth_flood
def test_deauth_flood_channel_pin_failure_is_fail_closed(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []

    def bad_set_channel(iface, ch):
        raise RuntimeError("iw not found")

    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=bad_set_channel,
                     clock=_Clock(), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=3)
    assert res.ok is False
    assert "channel pin failed" in res.reason
    assert sent == []


# FIX I2: falsy-zero channel
def test_deauth_flood_channel_zero_is_honoured(tmp_path):
    g = _bcast_gate(tmp_path)
    chans = []
    rf = BroadcastRF(gate=g, sender=lambda *a: None,
                     set_channel=lambda iface, ch: chans.append(ch),
                     clock=_Clock(step=3.0), sleep=lambda *_: None)
    rf.deauth_flood(channel=0, duration=3)
    assert chans == [0]


# FIX tests: default target is broadcast address
def test_deauth_flood_default_target_is_broadcast(tmp_path):
    from offense.rf_broadcast import BROADCAST  # re-exported via rf_targeted
    g = _bcast_gate(tmp_path)
    first_addr1 = []

    def cap_sender(frames, iface, count):
        if not first_addr1:
            from scapy.all import Dot11  # type: ignore
            first_addr1.append(frames[0][Dot11].addr1.lower())

    rf = BroadcastRF(gate=g, sender=cap_sender,
                     set_channel=lambda *a: None,
                     clock=_Clock(step=3.0), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=3)
    assert res.ok is True
    assert first_addr1[0] == BROADCAST.lower()


# FIX tests: honor_flag_off includes protected
def test_deauth_flood_honor_flag_off_includes_protected(tmp_path):
    cfg = {"lab_mode": True, "allow_broadcast": True, "broadcast_armed": True,
           "protect_bssids": ["aa:bb:cc:dd:ee:ff"],
           "broadcast": {"channel": 6, "max_tx_power_dbm": 5,
                         "max_burst_seconds": 3, "honor_protect_bssids": False}}
    g = Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")
    targets_seen = []

    def cap_sender(frames, iface, count):
        from scapy.all import Dot11  # type: ignore
        targets_seen.append(frames[0][Dot11].addr2.upper())

    rf = BroadcastRF(gate=g, sender=cap_sender,
                     set_channel=lambda *a: None,
                     clock=_Clock(step=3.0), sleep=lambda *_: None)
    res = rf.deauth_flood(duration=3, bssids=["AA:BB:CC:DD:EE:FF"])
    assert res.ok is True
    # flag off → protected BSSID must NOT be excluded
    assert "AA:BB:CC:DD:EE:FF" in targets_seen


# ---------------------------------------------------------------------------
# Task 3: beacon_spam
# ---------------------------------------------------------------------------

from scapy.all import Dot11Beacon, Dot11Elt  # type: ignore
from offense.rf_broadcast import build_beacon_frame


def test_build_beacon_frame_carries_ssid():
    f = build_beacon_frame("FreeWiFi", "02:11:22:33:44:55")
    assert f.haslayer(Dot11Beacon)
    elt = f.getlayer(Dot11Elt)
    assert elt.info == b"FreeWiFi"


def test_beacon_spam_denied_when_not_armed(tmp_path):
    g = _bcast_gate(tmp_path, allow_broadcast=False)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.beacon_spam(ssids=["A", "B"], duration=3)
    assert res.ok is False
    assert "allow_broadcast off" in res.reason
    assert sent == []


def test_beacon_spam_armed_transmits(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(1),
                     set_channel=lambda *a: None, clock=_Clock(step=3.0),
                     sleep=lambda *_: None)  # 1 burst
    res = rf.beacon_spam(ssids=["FreeWiFi", "Starbucks"], duration=3)
    assert res.ok is True
    assert len(sent) == 1      # one burst sent the SSID set


# FIX C2: channel pin fail-closed — beacon_spam
def test_beacon_spam_channel_pin_failure_is_fail_closed(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []

    def bad_set_channel(iface, ch):
        raise RuntimeError("iw not found")

    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=bad_set_channel,
                     clock=_Clock(), sleep=lambda *_: None)
    res = rf.beacon_spam(duration=3)
    assert res.ok is False
    assert "channel pin failed" in res.reason
    assert sent == []


# FIX tests: denied when broadcast_armed off
def test_beacon_spam_denied_when_broadcast_armed_off(tmp_path):
    g = _bcast_gate(tmp_path, broadcast_armed=False)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.beacon_spam(duration=3)
    assert res.ok is False
    assert sent == []


# ---------------------------------------------------------------------------
# Task 4: assoc_flood
# ---------------------------------------------------------------------------

from scapy.all import Dot11Auth  # type: ignore
from offense.rf_broadcast import build_auth_frame


def test_build_auth_frame():
    f = build_auth_frame("AA:BB:CC:DD:EE:FF", "02:00:00:00:00:01")
    assert f.haslayer(Dot11Auth)
    from scapy.all import Dot11  # type: ignore
    assert f[Dot11].addr1.upper() == "AA:BB:CC:DD:EE:FF"   # to the AP


def test_assoc_flood_refuses_protected_ap(tmp_path):
    g = _bcast_gate(tmp_path, protect_bssids=["aa:bb:cc:dd:ee:ff"])
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None)
    res = rf.assoc_flood("AA:BB:CC:DD:EE:FF", duration=3)
    assert res.ok is False
    assert "protected" in res.reason.lower()
    assert sent == []


def test_assoc_flood_armed_transmits(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda frames, iface, count: sent.append(1),
                     set_channel=lambda *a: None, clock=_Clock(step=3.0),
                     sleep=lambda *_: None)
    res = rf.assoc_flood("11:22:33:44:55:66", duration=3)
    assert res.ok is True
    assert len(sent) == 1


# FIX C2: channel pin fail-closed — assoc_flood
def test_assoc_flood_channel_pin_failure_is_fail_closed(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []

    def bad_set_channel(iface, ch):
        raise RuntimeError("iw not found")

    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=bad_set_channel,
                     clock=_Clock(), sleep=lambda *_: None)
    res = rf.assoc_flood("11:22:33:44:55:66", duration=3)
    assert res.ok is False
    assert "channel pin failed" in res.reason
    assert sent == []


# FIX I1: dry-run audit
def test_assoc_flood_dry_run(tmp_path):
    import json
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None,
                     dry_run=True)
    res = rf.assoc_flood("11:22:33:44:55:66", duration=3)
    assert res.ok is True and res.dry_run is True
    assert res.bursts == 0
    assert sent == []
    # verify audit record was written for the dry-run
    audit_path = tmp_path / "audit.jsonl"
    lines = audit_path.read_text().splitlines()
    dry_run_records = [json.loads(l) for l in lines
                       if "dry-run" in json.loads(l).get("reason", "")]
    assert any(r["action"] == "assoc_flood" for r in dry_run_records)


# FIX N1: spoofed MAC uniqueness
def test_assoc_flood_spoofed_macs_are_unique(tmp_path):
    g = _bcast_gate(tmp_path)
    captured_frames = []

    def cap_sender(frames, iface, count):
        if not captured_frames:
            captured_frames.extend(frames)

    rf = BroadcastRF(gate=g, sender=cap_sender,
                     set_channel=lambda *a: None,
                     clock=_Clock(step=3.0), sleep=lambda *_: None)
    rf.assoc_flood("11:22:33:44:55:66", duration=3, clients=16)
    from scapy.all import Dot11  # type: ignore
    macs = [f[Dot11].addr2.upper() for f in captured_frames]
    assert len(macs) == len(set(macs)), "spoofed MACs must be unique"


# ---------------------------------------------------------------------------
# Task 5: ble_spam
# ---------------------------------------------------------------------------

def test_ble_spam_denied_when_not_armed(tmp_path):
    g = _bcast_gate(tmp_path, lab_mode=False)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(), sleep=lambda *_: None)
    res = rf.ble_spam(duration=3)
    assert res.ok is False
    assert "lab_mode off" in res.reason
    assert sent == []


def test_ble_spam_armed_uses_ble_sender_timeboxed(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(step=1.0), sleep=lambda *_: None)
    res = rf.ble_spam(duration=999)            # capped to 3
    assert res.ok is True
    assert res.seconds == 3
    assert len(sent) == 3


def test_ble_spam_dry_run(tmp_path):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, ble_sender=lambda: sent.append(1),
                     clock=_Clock(), sleep=lambda *_: None, dry_run=True)
    res = rf.ble_spam(duration=3)
    assert res.ok is True and res.dry_run is True
    assert sent == []


# FIX I4: ble_spam NotImplemented → clean result
def test_ble_spam_no_sender_returns_error(tmp_path):
    """Armed gate, no ble_sender injected → ok=False with 'ble error' in reason."""
    g = _bcast_gate(tmp_path)
    # No ble_sender injected; default _ble_advert_send raises NotImplementedError
    rf = BroadcastRF(gate=g, clock=_Clock(step=3.0), sleep=lambda *_: None)
    res = rf.ble_spam(duration=3)
    assert res.ok is False
    assert "ble error" in res.reason


# ---------------------------------------------------------------------------
# Task 6: CLI
# ---------------------------------------------------------------------------

from offense.rf_broadcast import build_args, run_cli


def test_cli_deauth_flood_dry_run(tmp_path, capsys):
    g = _bcast_gate(tmp_path)
    sent = []
    rf = BroadcastRF(gate=g, sender=lambda *a: sent.append(a),
                     set_channel=lambda *a: None, clock=_Clock(), sleep=lambda *_: None,
                     dry_run=True)
    args = build_args(["--deauth-flood", "--duration", "3", "--no-tx"])
    rc = run_cli(args, rf=rf)
    assert rc == 0
    assert sent == []
    assert "dry-run" in capsys.readouterr().out.lower()


def test_cli_requires_action(tmp_path):
    g = _bcast_gate(tmp_path)
    rf = BroadcastRF(gate=g, clock=_Clock(), sleep=lambda *_: None, dry_run=True)
    assert run_cli(build_args([]), rf=rf) == 2
