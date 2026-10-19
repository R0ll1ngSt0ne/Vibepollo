#pragma once
namespace companion_integration_policy {
  // Legacy assignments retain protection until an explicit setting is saved.
  constexpr bool account_enabled(bool configured, bool enabled, bool legacy_assignments) {
    return configured ? enabled : legacy_assignments;
  }
}
