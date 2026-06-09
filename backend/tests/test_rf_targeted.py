"""Unit tests for Tier A targeted RF offense (no hardware; sender/sniffer injected)."""
from pathlib import Path

from scapy.all import Dot11, Dot11Deauth, EAPOL, RadioTap  # type: ignore

from offense.rf_targeted import BROADCAST, build_deauth_frames


def test_build_deauth_frames_both_directions():
    bssid, client = "AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"
    frames = build_deauth_frames(bssid, client, reason=7)
    assert len(frames) == 2  # AP->client and client->AP
    # AP -> client
    d0 = frames[0]
    assert d0.haslayer(Dot11Deauth)
    assert d0[Dot11].addr1.upper() == client      # receiver
    assert d0[Dot11].addr2.upper() == bssid        # transmitter
    assert d0[Dot11].addr3.upper() == bssid        # BSSID
    assert d0[Dot11Deauth].reason == 7
    # client -> AP
    d1 = frames[1]
    assert d1[Dot11].addr1.upper() == bssid
    assert d1[Dot11].addr2.upper() == client
    assert d1[Dot11].addr3.upper() == bssid


def test_build_deauth_broadcast_client_single_frame():
    frames = build_deauth_frames("AA:BB:CC:DD:EE:FF", BROADCAST, reason=7)
    # broadcast deauth only makes sense AP->all; one frame
    assert len(frames) == 1
    assert frames[0][Dot11].addr1.upper() == BROADCAST.upper()


# ---------------------------------------------------------------------------
# Task 2: TargetedRF.deauth
# ---------------------------------------------------------------------------
from kuma_core.authz import Gate
from offense.rf_targeted import TargetedRF


def _armed_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


def test_deauth_authorized_calls_sender(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, iface="wlan1mon",
                    sender=lambda frames, iface, count: sent.append((len(frames), iface, count)))
    res = rf.deauth("AA:BB:CC:DD:EE:FF", client="11:22:33:44:55:66", count=8)
    assert res.ok is True
    assert sent == [(2, "wlan1mon", 8)]          # 2 frames, our iface, count passed through
    assert res.frames_sent == 16                  # 2 frames * 8 bursts


def test_deauth_unauthorized_does_not_transmit(tmp_path):
    sent = []
    g = _armed_gate(tmp_path)                      # empty approved_targets
    rf = TargetedRF(gate=g, iface="wlan1mon",
                    sender=lambda *a: sent.append(a))
    res = rf.deauth("99:99:99:99:99:99")
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert sent == []                              # NEVER transmitted


def test_deauth_protected_bssid_refused(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"],
                    protect_bssids=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, sender=lambda *a: sent.append(a))
    res = rf.deauth("AA:BB:CC:DD:EE:FF")
    assert res.ok is False
    assert "hard deny" in res.reason
    assert sent == []


def test_deauth_dry_run_builds_but_does_not_send(tmp_path):
    sent = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, sender=lambda *a: sent.append(a), dry_run=True)
    res = rf.deauth("AA:BB:CC:DD:EE:FF")
    assert res.ok is True
    assert res.dry_run is True
    assert res.frames_sent == 0
    assert sent == []                              # dry run never transmits


# ---------------------------------------------------------------------------
# Task 3: TargetedRF.capture_handshake
# ---------------------------------------------------------------------------

def _fake_eapol(bssid="AA:BB:CC:DD:EE:FF", client="11:22:33:44:55:66"):
    return RadioTap() / Dot11(addr1=client, addr2=bssid, addr3=bssid) / EAPOL()


def test_capture_authorized_writes_pcap(tmp_path):
    chans = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(
        gate=g, iface="wlan1mon",
        set_channel=lambda iface, ch: chans.append((iface, ch)),
        sniffer=lambda iface, bssid, timeout: [_fake_eapol(), _fake_eapol()],
        sender=lambda *a: None)
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "handshakes")
    assert res.ok is True
    assert chans == [("wlan1mon", 6)]                   # tuned to the channel first
    assert res.frames_captured == 2                     # FIX 3: EAPOL frames RECEIVED
    pcaps = list((tmp_path / "handshakes").glob("*.pcap"))
    assert len(pcaps) == 1
    assert "AABBCCDDEEFF" in pcaps[0].name.replace(":", "").upper()


def test_capture_unauthorized_refused_no_sniff(tmp_path):
    sniffed = []
    g = _armed_gate(tmp_path)                           # nothing approved
    rf = TargetedRF(gate=g,
                    set_channel=lambda *a: None,
                    sniffer=lambda *a: sniffed.append(a) or [])
    res = rf.capture_handshake("99:99:99:99:99:99", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert sniffed == []                                # never even tuned/sniffed


def test_capture_no_eapol_reports_empty(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, set_channel=lambda *a: None,
                    sniffer=lambda *a: [])
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is True
    assert res.frames_captured == 0                     # FIX 3: no EAPOL received
    assert "no eapol" in res.reason.lower()
    assert list((tmp_path / "h").glob("*.pcap")) == []  # nothing to write


def test_capture_dry_run_does_not_tune_or_sniff(tmp_path):
    chans = []
    sniffed = []
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(
        gate=g, iface="wlan1mon",
        set_channel=lambda iface, ch: chans.append(ch),
        sniffer=lambda *a: sniffed.append(a) or [],
        dry_run=True)
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is True
    assert res.dry_run is True
    assert res.frames_sent == 0
    assert chans == []       # channel NOT tuned in dry run
    assert sniffed == []     # sniffer NOT called in dry run


def test_deauth_sender_exception_returns_error_not_crash(tmp_path):
    def boom(*a): raise RuntimeError("nic gone")
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, sender=boom)
    res = rf.deauth("AA:BB:CC:DD:EE:FF")
    assert res.ok is False
    assert "tx error" in res.reason


def test_capture_sniffer_exception_returns_error_not_crash(tmp_path):
    def boom(*a): raise RuntimeError("sniff fail")
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    rf = TargetedRF(gate=g, set_channel=lambda *a: None, sniffer=boom)
    res = rf.capture_handshake("AA:BB:CC:DD:EE:FF", channel=6, timeout=1,
                               out_dir=tmp_path / "h")
    assert res.ok is False
    assert "capture error" in res.reason


# ---------------------------------------------------------------------------
# Task 4: CLI
# ---------------------------------------------------------------------------
from offense.rf_targeted import build_args, run_cli


def test_cli_deauth_dryrun_routes_to_deauth(tmp_path, capsys):
    g = _armed_gate(tmp_path, approved_targets=["aa:bb:cc:dd:ee:ff"])
    calls = []
    rf = TargetedRF(gate=g, sender=lambda *a: calls.append("sent"), dry_run=True)
    args = build_args(["--bssid", "AA:BB:CC:DD:EE:FF", "--deauth",
                       "--client", "11:22:33:44:55:66", "--count", "4", "--no-tx"])
    rc = run_cli(args, rf=rf)
    assert rc == 0
    assert calls == []                       # dry-run: nothing sent
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()


def test_cli_requires_an_action(tmp_path):
    g = _armed_gate(tmp_path)
    rf = TargetedRF(gate=g, sender=lambda *a: None, dry_run=True)
    args = build_args(["--bssid", "AA:BB:CC:DD:EE:FF"])  # no --deauth/--capture
    rc = run_cli(args, rf=rf)
    assert rc == 2                            # usage error


# ---------------------------------------------------------------------------
# Task 5: gitignore
# ---------------------------------------------------------------------------
def test_handshakes_dir_is_gitignored():
    gi = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    # backend/data/ (the broad runtime-data ignore) covers data/handshakes/.
    assert "backend/data/" in gi
