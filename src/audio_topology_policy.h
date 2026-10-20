#pragma once

#include <array>
#include <cstddef>
#include <string>

namespace audio::policy {
  // Notifications carry no actor identity. Only a transition away from an
  // observed unavailable endpoint is a recovery candidate. An unexplained
  // change adopts the newer selection; never infer ownership from inequality.
  template<class Endpoint, std::size_t Count>
  struct topology_snapshot_t {
    std::array<Endpoint, Count> preferred {};
    std::array<Endpoint, Count> current {};
    std::array<bool, Count> displaced {};

    void capture(const std::array<Endpoint, Count> &ids) {
      preferred = current = ids;
      displaced.fill(false);
    }

    void observe(std::size_t role, const Endpoint &next, bool previous_available) {
      if (role >= Count || current[role] == next) return;
      if (previous_available || (current[role].empty() && !displaced[role])) {
        preferred[role] = next;
        displaced[role] = false;
      } else {
        displaced[role] = !preferred[role].empty();
      }
      current[role] = next;
      if (next == preferred[role]) displaced[role] = false;
    }

    bool pending(std::size_t role) const {
      return displaced[role] && !preferred[role].empty() &&
             !current[role].empty() && preferred[role] != current[role];
    }
  };
}
