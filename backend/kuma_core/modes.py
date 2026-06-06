"""The KUMA mode engine.

Five first-class modes drive both behaviour and the bear's face. This is the
defensive inversion of Pwnagotchi's mood->face state machine: where Pwnagotchi
picks a face from how well it's *pwning*, KUMA picks one from how worried it
should be about the environment.

    Hibernate = conserve
    Foraging  = discover
    Honey     = deceive
    Sentinel  = detect
    Apex      = respond

Mode switching is clean, logged, and validated against a known set. The engine
holds no packet-capture state — detectors do — so it stays trivially testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VALID_MODES = ("hibernate", "foraging", "honey", "sentinel", "apex")


@dataclass(frozen=True)
class ModeSpec:
    name: str
    display_name: str
    description: str
    bear_state: str
    allowed_actions: tuple[str, ...]


_COMMON_ENTRIES = (
    "enter_hibernate", "enter_foraging", "enter_honey",
    "enter_sentinel", "enter_apex",
)

MODES: dict[str, ModeSpec] = {
    "hibernate": ModeSpec(
        "hibernate", "Hibernate Mode",
        "Low-power idle watch. Minimal scanning, low-rate heartbeat.",
        "sleeping",
        ("acknowledge_alert", "export_events", *_COMMON_ENTRIES),
    ),
    "foraging": ModeSpec(
        "foraging", "Foraging Mode",
        "Discovery and inventory. Builds the trusted baseline.",
        "foraging",
        ("acknowledge_alert", "start_mock_capture", "export_events",
         *_COMMON_ENTRIES),
    ),
    "honey": ModeSpec(
        "honey", "Honey Mode",
        "Deception. Simulated decoy telemetry (mock-only in v0.0).",
        "honey_trap",
        ("acknowledge_alert", "start_mock_capture", "export_events",
         "clear_mock_events", *_COMMON_ENTRIES),
    ),
    "sentinel": ModeSpec(
        "sentinel", "Sentinel Mode",
        "Defensive monitoring, alerting, and evidence logging.",
        "suspicious",
        ("acknowledge_alert", "start_mock_capture", "export_events",
         "clear_mock_events", *_COMMON_ENTRIES),
    ),
    "apex": ModeSpec(
        "apex", "Apex Mode",
        "Controlled action framework. Lab-mode + allowlist + confirm only.",
        "apex_ready",
        ("acknowledge_alert", "export_events", *_COMMON_ENTRIES),
    ),
}


@dataclass
class ModeEngine:
    """Holds the current mode and validates transitions."""

    current: str = "sentinel"
    history: list[dict] = field(default_factory=list)

    def spec(self) -> ModeSpec:
        return MODES[self.current]

    def bear_state(self) -> str:
        return self.spec().bear_state

    def allowed_actions(self) -> tuple[str, ...]:
        return self.spec().allowed_actions

    def is_valid(self, mode: str) -> bool:
        return mode in VALID_MODES

    def switch(self, mode: str) -> ModeSpec:
        """Switch modes. Raises ValueError on an unknown mode."""
        if not self.is_valid(mode):
            raise ValueError(f"unknown mode: {mode!r}")
        previous = self.current
        self.current = mode
        self.history.append({"from": previous, "to": mode})
        return self.spec()

    def describe(self) -> dict:
        s = self.spec()
        return {
            "mode": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "bear_state": s.bear_state,
            "allowed_actions": list(s.allowed_actions),
        }
