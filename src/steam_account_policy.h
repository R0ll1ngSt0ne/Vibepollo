#pragma once

#include <algorithm>
#include <string_view>
#include <mutex>

namespace steam_account_policy {
  inline std::recursive_mutex &launch_mutex() {
    static std::recursive_mutex mutex;
    return mutex;
  }
  // Public-universe individual SteamID64, represented as text to avoid JS
  // number precision loss. Empty removes an assignment. No auth material.
  inline bool valid_assignment(std::string_view value) {
    return value.empty() ||
           (value.size() == 17 &&
            std::all_of(value.begin(), value.end(), [](char c) { return c >= '0' && c <= '9'; }) &&
            value > std::string_view {"76561197960265728"} &&
            value <= std::string_view {"76561202255233023"});
  }
}
