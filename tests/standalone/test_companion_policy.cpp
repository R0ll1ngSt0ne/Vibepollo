// Dependency-free native smoke/regression checks. Does not touch Windows state.
#include "../../src/audio_policy.h"
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
  std::array<std::wstring, 3> original {L"monitor", L"", L"headset"};
  const std::array<std::wstring, 3> later {L"fallback", L"speakers", L"stream"};
  audio::policy::fill_missing_role_snapshot(original, later);
  assert(original[0] == L"monitor");
  assert(original[1] == L"speakers");
  assert(original[2] == L"headset");
  audio::policy::fill_missing_role_snapshot(original, later);
  assert(original[0] == L"monitor");
  std::cout << "SteamID boundary validation and immutable role snapshot: PASS\n";
}
