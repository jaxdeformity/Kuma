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
