"""Unit tests for Tier A network offense (no targets/deps; clients injected)."""
from pathlib import Path

import json

from kuma_core.authz import Gate
from offense.net_offense import (
    ATTEMPTERS,
    BruteResult,
    DEFAULT_PASSWORDS,
    DEFAULT_PORTS,
    DEFAULT_USERS,
    NetworkOffense,
    ScanResult,
    StealResult,
    _loot_path,
    _telnet_success,
    build_args,
    load_wordlists,
    parse_nmap_ports,
    run_cli,
)


# ---------------------------------------------------------------------------
# Task 1 — wordlists
# ---------------------------------------------------------------------------

def test_default_wordlists_nonempty():
    assert "root" in DEFAULT_USERS
    assert "admin" in DEFAULT_USERS
    assert len(DEFAULT_PASSWORDS) >= 5
    users, passwords = load_wordlists()
    assert users == DEFAULT_USERS
    assert passwords == DEFAULT_PASSWORDS


def test_wordlist_config_override(tmp_path):
    ul = tmp_path / "u.txt"; ul.write_text("alice\nbob\n", encoding="utf-8")
    pl = tmp_path / "p.txt"; pl.write_text("hunter2\n\n  spaces  \n", encoding="utf-8")
    users, passwords = load_wordlists({"bruteforce": {"userlist": str(ul),
                                                      "passlist": str(pl)}})
    assert users == ["alice", "bob"]
    assert passwords == ["hunter2", "spaces"]      # blank lines dropped, trimmed


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _armed_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


# ---------------------------------------------------------------------------
# Task 2 — bruteforce gating + injection
# ---------------------------------------------------------------------------

def test_bruteforce_finds_creds_and_stops(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    attempts = []
    def fake(host, port, user, pwd, timeout):
        attempts.append((user, pwd))
        return user == "root" and pwd == "toor"
    no = NetworkOffense(gate=g, attempters={"ssh": fake})
    res = no.bruteforce("192.168.50.162", "ssh",
                        users=["root"], passwords=["x", "toor", "y"])
    assert res.ok is True
    assert res.found == [("root", "toor")]
    assert ("root", "y") not in attempts        # stopped after success
    assert res.attempts == 2                      # x (fail), toor (hit)


def test_bruteforce_unauthorized_makes_no_attempts(tmp_path):
    g = _armed_gate(tmp_path)                      # nothing approved
    attempts = []
    no = NetworkOffense(gate=g,
                        attempters={"ssh": lambda *a: attempts.append(a) or True})
    res = no.bruteforce("10.0.0.9", "ssh", users=["root"], passwords=["root"])
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert attempts == []                          # never connected


def test_bruteforce_unknown_protocol(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g, attempters={"ssh": lambda *a: True})
    res = no.bruteforce("192.168.50.5", "gopher")
    assert res.ok is False
    assert "unknown proto" in res.reason


def test_bruteforce_dry_run_no_attempts(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    attempts = []
    no = NetworkOffense(gate=g, attempters={"ssh": lambda *a: attempts.append(a) or True},
                        dry_run=True)
    res = no.bruteforce("192.168.50.5", "ssh", users=["root"], passwords=["root"])
    assert res.ok is True and res.dry_run is True
    assert attempts == []
    assert res.attempts == 0


# ---------------------------------------------------------------------------
# Task 3 — real attempters registry
# ---------------------------------------------------------------------------

def test_all_six_protocols_registered():
    assert set(ATTEMPTERS) == {"ssh", "ftp", "smb", "rdp", "telnet", "sql"}
    for fn in ATTEMPTERS.values():
        assert callable(fn)


def test_default_registry_used_when_not_injected(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g)
    assert set(no.attempters) == {"ssh", "ftp", "smb", "rdp", "telnet", "sql"}


def test_bruteforce_dispatches_to_named_protocol(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    called = {}
    def make(tag):
        def fn(host, port, user, pwd, timeout):
            called["tag"] = tag; called["port"] = port; return False
        return fn
    no = NetworkOffense(gate=g, attempters={k: make(k) for k in DEFAULT_PORTS})
    no.bruteforce("192.168.50.5", "smb", users=["x"], passwords=["y"])
    assert called["tag"] == "smb"
    assert called["port"] == 445          # default SMB port used


# ---------------------------------------------------------------------------
# Task 4 — scan
# ---------------------------------------------------------------------------

def test_parse_nmap_ports():
    sample = (
        "Starting Nmap\n"
        "22/tcp open ssh\n"
        "80/tcp closed http\n"
        "445/tcp open microsoft-ds\n"
        "Nmap done\n")
    assert parse_nmap_ports(sample) == [22, 445]


def test_scan_authorized_uses_runner(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g, scanner=lambda host, ports, timeout: [22, 445])
    res = no.scan("192.168.50.162")
    assert res.ok is True
    assert res.open_ports == [22, 445]


def test_scan_unauthorized_does_not_run(tmp_path):
    ran = []
    g = _armed_gate(tmp_path)
    no = NetworkOffense(gate=g, scanner=lambda *a: ran.append(a) or [])
    res = no.scan("8.8.8.8")
    assert res.ok is False
    assert "not in authorized set" in res.reason
    assert ran == []


# ---------------------------------------------------------------------------
# Task 5 — steal_ssh
# ---------------------------------------------------------------------------

def test_steal_authorized_uses_stealer(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    got = {}
    def fake(host, port, user, pwd, remote_paths, out_dir, timeout):
        got["args"] = (host, port, user, list(remote_paths))
        return ["/etc/passwd"]
    no = NetworkOffense(gate=g, stealer=fake)
    res = no.steal_ssh("192.168.50.162", "root", "toor", ["/etc/passwd"],
                       out_dir=tmp_path / "loot")
    assert res.ok is True
    assert res.files == ["/etc/passwd"]
    assert got["args"][0] == "192.168.50.162"


def test_steal_unauthorized_no_connection(tmp_path):
    ran = []
    g = _armed_gate(tmp_path)
    no = NetworkOffense(gate=g, stealer=lambda *a: ran.append(a) or [])
    res = no.steal_ssh("1.1.1.1", "root", "x", ["/etc/passwd"], out_dir=tmp_path)
    assert res.ok is False
    assert ran == []


def test_steal_dry_run(tmp_path):
    ran = []
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g, stealer=lambda *a: ran.append(a) or [], dry_run=True)
    res = no.steal_ssh("192.168.50.5", "root", "x", ["/etc/passwd"], out_dir=tmp_path)
    assert res.ok is True and res.dry_run is True
    assert ran == []


# ---------------------------------------------------------------------------
# Task 6 — CLI
# ---------------------------------------------------------------------------

def test_cli_brute_dry_run(tmp_path, capsys):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    calls = []
    no = NetworkOffense(gate=g, attempters={"ssh": lambda *a: calls.append(a) or True},
                        dry_run=True)
    args = build_args(["--host", "192.168.50.5", "--brute", "ssh", "--no-tx"])
    rc = run_cli(args, no=no)
    assert rc == 0
    assert calls == []
    assert "dry-run" in capsys.readouterr().out.lower()


def test_cli_requires_action(tmp_path):
    g = _armed_gate(tmp_path)
    no = NetworkOffense(gate=g, dry_run=True)
    args = build_args(["--host", "192.168.50.5"])
    assert run_cli(args, no=no) == 2


# ---------------------------------------------------------------------------
# Task 7 — requirements file + gitignore
# ---------------------------------------------------------------------------

def test_offense_requirements_and_loot_ignored():
    root = Path(__file__).resolve().parents[2]
    reqs = (root / "backend" / "requirements-offense.txt").read_text(encoding="utf-8")
    for dep in ("paramiko", "impacket", "pymysql"):
        assert dep in reqs
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "backend/data/loot/" in gi


# ---------------------------------------------------------------------------
# FIX 1 — scan audit
# ---------------------------------------------------------------------------

def test_scan_is_audited(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g, scanner=lambda host, ports, timeout: [22, 445])
    res = no.scan("192.168.50.10")
    assert res.ok is True
    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists(), "audit file not written"
    lines = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    scan_entries = [e for e in lines if e.get("action") == "scan"]
    assert scan_entries, "no audit entry with action='scan'"
    assert scan_entries[-1]["target"] == "192.168.50.10"


# ---------------------------------------------------------------------------
# FIX 2 — telnet success heuristic (pure helper)
# ---------------------------------------------------------------------------

def test_telnet_success_empty_is_false():
    assert _telnet_success(b"") is False


def test_telnet_success_short_prompt_is_false():
    assert _telnet_success(b"$ ") is False  # len==2, <=4


def test_telnet_no_prompt_is_not_success():
    # Server sends nothing — recv returns b"" immediately, resp stays empty
    assert _telnet_success(b"") is False


def test_telnet_success_incorrect_is_false():
    assert _telnet_success(b"Login incorrect, try again") is False


def test_telnet_success_failed_is_false():
    assert _telnet_success(b"Authentication failed for user") is False


def test_telnet_success_login_prompt_is_false():
    assert _telnet_success(b"login: ") is False


def test_telnet_success_shell_prompt_is_true():
    assert _telnet_success(b"user@host:~$ ") is True


# ---------------------------------------------------------------------------
# FIX 3 — loot path containment (pure helper)
# ---------------------------------------------------------------------------

def test_loot_path_normal(tmp_path):
    result = _loot_path(tmp_path, "192.168.1.1", "/etc/passwd")
    assert result is not None
    assert str(result).startswith(str(tmp_path.resolve()))
    assert result.name == "192_168_1_1_passwd"


def test_loot_path_traversal_blocked(tmp_path):
    # A crafted remote filename trying to escape out_dir
    result = _loot_path(tmp_path, "192.168.1.1", "/../../../etc/evil")
    # Path(rp).name strips dirs, so "evil" lands safely — this should be fine
    assert result is not None
    assert str(result).startswith(str(tmp_path.resolve()))


def test_loot_path_name_only_used(tmp_path):
    # Confirm Path(rp).name is used — directory components are stripped
    result = _loot_path(tmp_path, "10.0.0.1", "/some/deep/dir/secret.key")
    assert result is not None
    assert result.name == "10_0_0_1_secret.key"


# ---------------------------------------------------------------------------
# FIX 5 — coverage gaps
# ---------------------------------------------------------------------------

def test_bruteforce_attempter_raises_continues(tmp_path):
    """An attempter that raises on one attempt must not abort the run."""
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    call_count = [0]
    def flaky(host, port, user, pwd, timeout):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("simulated network error")
        # 4th call is success
        return call_count[0] == 4
    no = NetworkOffense(gate=g, attempters={"ssh": flaky})
    res = no.bruteforce("192.168.50.1", "ssh",
                        users=["u1", "u2"], passwords=["p1", "p2"],
                        stop_on_success=False)
    assert call_count[0] == 4
    assert res.attempts == 4
    assert len(res.found) == 1   # only the 4th succeeds


def test_bruteforce_stop_on_success_false_multi_user(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    valid = {("alice", "secret"), ("bob", "pass")}
    attempt_count = [0]
    def attempter(host, port, user, pwd, timeout):
        attempt_count[0] += 1
        return (user, pwd) in valid
    no = NetworkOffense(gate=g, attempters={"ssh": attempter})
    res = no.bruteforce("192.168.50.1", "ssh",
                        users=["alice", "bob"],
                        passwords=["wrong", "secret", "pass"],
                        stop_on_success=False)
    assert ("alice", "secret") in res.found
    assert ("bob", "pass") in res.found
    assert res.attempts == 6   # 2 users * 3 passwords


def test_bruteforce_audited(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    no = NetworkOffense(gate=g, attempters={"ssh": lambda *a: True})
    res = no.bruteforce("192.168.50.2", "ssh",
                        users=["root"], passwords=["root"])
    assert res.ok is True
    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    lines = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    brute_entries = [e for e in lines if "brute" in e.get("action", "")]
    assert brute_entries, "no brute audit entry written"
    assert brute_entries[-1]["target"] == "192.168.50.2"


def test_steal_audited(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    def fake_stealer(host, port, user, pwd, remote_paths, out_dir, timeout):
        return list(remote_paths)
    no = NetworkOffense(gate=g, stealer=fake_stealer)
    res = no.steal_ssh("192.168.50.3", "root", "toor", ["/etc/shadow"],
                       out_dir=tmp_path / "loot")
    assert res.ok is True
    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    lines = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    steal_entries = [e for e in lines if e.get("action") == "steal"]
    assert steal_entries, "no steal audit entry written"
    assert steal_entries[-1]["target"] == "192.168.50.3"


def test_rdp_dispatch_uses_injected_attempter(tmp_path):
    """Injected RDP attempter is called with correct port; no subprocess runs."""
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    record = {}
    def fake_rdp(host, port, user, pwd, timeout):
        record["host"] = host
        record["port"] = port
        return False
    no = NetworkOffense(gate=g, attempters={"rdp": fake_rdp})
    res = no.bruteforce("192.168.50.5", "rdp",
                        users=["admin"], passwords=["pass"])
    assert record.get("port") == 3389
    assert record.get("host") == "192.168.50.5"
    # Result is ok (gate passed) even though no cred found
    assert res.ok is True
