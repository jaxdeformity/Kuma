// KUMA Guard M5Core - mode + bear-state enums (mirror the backend).
#pragma once

enum class KumaMode { Hibernate, Foraging, Honey, Sentinel, Apex, Unknown };

// Bear faces, driven by backend `bear_state`. Inversion of Pwnagotchi's
// mood->face idea: the face reflects how worried KUMA is, not how well it pwns.
enum class BearState {
  Sleeping,    // hibernate
  Foraging,    // foraging
  HoneyTrap,   // honey
  Suspicious,  // sentinel, calm
  Alert,       // sentinel, high threat
  ApexReady,   // apex
  Logging,     // capture/logging
  Error        // backend unreachable
};

KumaMode modeFromString(const char* s);
BearState bearStateFromString(const char* s);
const char* modeName(KumaMode m);
