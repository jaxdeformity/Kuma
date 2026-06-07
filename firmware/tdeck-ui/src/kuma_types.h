// KUMA Guard T-Deck - shared mode / bear-state types (mirror the backend).
#pragma once
#include <Arduino.h>

enum class KumaMode { Hibernate, Foraging, Honey, Sentinel, Apex, Unknown };

enum class BearState {
  Sleeping, Foraging, HoneyTrap, Suspicious, Alert, ApexReady, Logging, Error
};

KumaMode    modeFromString(const String& s);
const char* modeName(KumaMode m);          // backend string ("sentinel" ...)
const char* modeLabel(KumaMode m);         // display label ("Sentinel")
BearState   bearStateFromString(const String& s);
