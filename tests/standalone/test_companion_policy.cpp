// Dependency-free native smoke/regression checks. Does not touch Windows state.
#include "../../src/audio_role_control.h"
#include "../../src/steam_account_policy.h"
#include <cassert>
#include <iostream>

int main() {
  using steam_account_policy::valid_assignment;
  assert(valid_assignment(""));
  assert(valid_assignment("76561197960265729"));
  assert(valid_assignment("76561202255233023"));
  assert(!valid_assignment("76561197960265728"));
  assert(!valid_assignment("76561202255233024"));
  assert(!valid_assignment("7656119796026572x"));
  assert(!valid_assignment(" 76561197960265729"));
  assert(!valid_assignment("account-name"));
  using roles_t = audio::role_control_t<std::size_t, 3>;
  const roles_t::ids_t original {L"monitor", L"", L"headset"};
  roles_t::ids_t current {L"fallback", L"speakers", L"stream"};
  roles_t::registry_t registry;
  roles_t::device_api_t devices;
  devices.defaults = [&] { return current; };
  devices.write = [&](std::size_t role, const std::wstring &id) {
    current[role] = id;
    return 0L;
  };
  devices.retire = [](std::jthread) {};
  roles_t control(registry, std::move(devices));
  control.capture(original);
  assert(control.assign(L"stream") == 0);
  assert(control.captured()[0] == L"monitor");
  // Upstream preserves the complete pre-display snapshot, including unknown
  // roles; later fallbacks must not become an invented restoration baseline.
  assert(control.captured()[1].empty());
  assert(control.captured()[2] == L"headset");
  assert(control.assign(L"stream") == 0);
  assert(control.captured() == original);
  assert(control.restore() == 0);
  assert(current[0] == L"monitor");
  assert(current[1] == L"stream");
  assert(current[2] == L"headset");
  std::cout << "SteamID boundary validation and immutable role snapshot: PASS\n";
}
