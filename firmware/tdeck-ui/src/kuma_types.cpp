#include "kuma_types.h"

KumaMode modeFromString(const String& s) {
  if (s == "hibernate") return KumaMode::Hibernate;
  if (s == "foraging")  return KumaMode::Foraging;
  if (s == "honey")     return KumaMode::Honey;
  if (s == "sentinel")  return KumaMode::Sentinel;
  if (s == "apex")      return KumaMode::Apex;
  return KumaMode::Unknown;
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

const char* modeLabel(KumaMode m) {
  switch (m) {
    case KumaMode::Hibernate: return "Hibernate";
    case KumaMode::Foraging:  return "Foraging";
    case KumaMode::Honey:     return "Honey";
    case KumaMode::Sentinel:  return "Sentinel";
    case KumaMode::Apex:      return "Apex";
    default:                  return "Unknown";
  }
}

BearState bearStateFromString(const String& s) {
  if (s == "sleeping")   return BearState::Sleeping;
  if (s == "foraging")   return BearState::Foraging;
  if (s == "honey_trap") return BearState::HoneyTrap;
  if (s == "suspicious") return BearState::Suspicious;
  if (s == "alert")      return BearState::Alert;
  if (s == "apex_ready") return BearState::ApexReady;
  if (s == "logging")    return BearState::Logging;
  return BearState::Error;
}
