"""Host-based detector: SSH brute-force from the LAN -> KUMA event.

KUMA's wifi monitor (live_capture) watches 802.11 management frames. IP-layer
attackers - like a **Bjorn** unit - don't deauth; they join the LAN and brute-
force the Pi's own services (SSH/FTP/SMB...). This detector tails the SSH
journal, counts failed-auth floods per source IP, and emits a KUMA event so the
bear reacts to a LAN intrusion the same way it reacts to an RF attack.

It seeds from recent backlog (so a brute-force that already happened is caught
on start) and then follows live.

Run (on the Pi, as root, from backend/):
    sudo ./.venv/bin/python -m detectors.auth_watch
"""
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import time

from kuma_core import database, events

# "Failed password for [invalid user ]<user> from <ip> port ..."
# "Invalid user <user> from <ip> port ..."
_FAIL = re.compile(
    r"(?:Failed password for (?:invalid user )?(?P<u1>\S+)|"
    r"Invalid user (?P<u2>\S+)|"
    r"authentication failure;.*?ruser=).*?from (?P<ip>\d+\.\d+\.\d+\.\d+)")
_FAIL_IP = re.compile(r"(?:Failed password|Invalid user|Connection closed by "
                      r"(?:authenticating|invalid) user).*?from (?P<ip>\d+\.\d+\.\d+\.\d+)")

WINDOW = 120          # sliding window seconds
THRESHOLD = 10        # failed attempts from one IP within WINDOW -> brute force
COOLDOWN = 300        # min seconds between alerts for the same IP


class BruteForceTracker:
    """Per-source-IP sliding window of failed SSH auths."""

    def __init__(self) -> None:
        self.hits: dict[str, collections.deque[float]] = collections.defaultdict(
            collections.deque)
        self.users: dict[str, collections.Counter] = collections.defaultdict(
            collections.Counter)
        self.last_emit: dict[str, float] = {}

    def add(self, ip: str, user: str | None) -> dict | None:
        now = time.time()
        dq = self.hits[ip]
        dq.append(now)
        if user:
            self.users[ip][user] += 1
        cutoff = now - WINDOW
        while dq and dq[0] < cutoff:
            dq.popleft()
        count = len(dq)
        if count < THRESHOLD or now - self.last_emit.get(ip, 0) < COOLDOWN:
            return None
        self.last_emit[ip] = now
        top_users = [u for u, _ in self.users[ip].most_common(6)]
        conf = min(96, 60 + count)
        ev = events.make_event(
            mode="sentinel", event_type="ssh_bruteforce",
            confidence=conf, severity="high",
            message=f"SSH brute-force from {ip}: {count} failed logins in "
                    f"{WINDOW}s (users: {', '.join(top_users) or '?'})",
            source=ip, target="kuma1",
            raw_json={"src_ip": ip, "fail_count": count,
                      "window_seconds": WINDOW, "users_tried": top_users,
                      "detector": "auth_watch"})
        dq.clear()
        return ev


def _journal(backlog: int):
    """Follow the SSH journal, seeded with `backlog` lines, yielding text."""
    cmd = ["journalctl", "-u", "ssh", "-u", "ssh.service", "-n", str(backlog),
           "-f", "-o", "cat", "--no-pager"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True,
                            bufsize=1)
    try:
        for line in proc.stdout:                      # type: ignore[union-attr]
            yield line.rstrip("\n")
    finally:
        proc.terminate()


def run(backlog: int = 5000) -> None:
    database.init_db()
    tracker = BruteForceTracker()
    print(f"[auth_watch] watching SSH journal "
          f"(threshold={THRESHOLD} fails/{WINDOW}s, backlog={backlog})",
          flush=True)
    for line in _journal(backlog):
        m = _FAIL.search(line) or _FAIL_IP.search(line)
        if not m:
            continue
        ip = m.group("ip")
        user = m.groupdict().get("u1") or m.groupdict().get("u2")
        ev = tracker.add(ip, user)
        if ev:
            eid = database.insert_event(ev)
            print(f"[{ev['severity'].upper()}] {ev['event_type']} "
                  f"conf={ev['confidence']} -> event #{eid}: {ev['message']}",
                  flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="KUMA SSH brute-force detector")
    ap.add_argument("--backlog", type=int, default=5000,
                    help="journal lines to seed from (catches recent attacks)")
    run(ap.parse_args().backlog)


if __name__ == "__main__":
    main()
