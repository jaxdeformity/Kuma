// KUMA Guard M5Core - mode/bear-state string mapping (mirrors backend).
#include "modes.h"
#include <string.h>

KumaMode modeFromString(const char* s) {
  if (!s) return KumaMode::Unknown;
  if (!strcmp(s, "hibernate")) return KumaMode::Hibernate;
  if (!strcmp(s, "foraging"))  return KumaMode::Foraging;
  if (!strcmp(s, "honey"))     return KumaMode::Honey;
  if (!strcmp(s, "sentinel"))  return KumaMode::Sentinel;
  if (!strcmp(s, "apex"))      return KumaMode::Apex;
  return KumaMode::Unknown;
}

BearState bearStateFromString(const char* s) {
  if (!s) return BearState::Error;
  if (!strcmp(s, "sleeping"))   return BearState::Sleeping;
  if (!strcmp(s, "foraging"))   return BearState::Foraging;
  if (!strcmp(s, "honey_trap")) return BearState::HoneyTrap;
  if (!strcmp(s, "suspicious")) return BearState::Suspicious;
  if (!strcmp(s, "alert"))      return BearState::Alert;
  if (!strcmp(s, "apex_ready")) return BearState::ApexReady;
  if (!strcmp(s, "logging"))    return BearState::Logging;
  return BearState::Error;
}

const char* modeName(KumaMode m) {
  switch (m) {
    case KumaMode::Hibernate: return "hibernate";
    case KumaMode::Foraging:  return "foraging";
    case KumaMode::Honey:     return "honey";
    case KumaMode::Sentinel:  return "sentinel";
    case KumaMode::Apex:      return "apex";
    default:                  return "unknown";
  }
}
