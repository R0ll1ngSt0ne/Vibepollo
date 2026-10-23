#pragma once

#include <cstddef>
#include <mutex>
#include <set>
#include <utility>

namespace hook_execution {
  // Only process creation is serialized with closing the session. Waiting for
  // a hook to exit must happen outside this lock and the account policy lock.
  class session {
  public:
    explicit session(std::set<std::size_t> outstanding = {}) : started_(std::move(outstanding)) {}
    template<class Spawn>
    bool start(std::size_t index, Spawn &&spawn) {
      std::lock_guard lock(mutex_);
      if (closed_ || !spawn()) return false;
      started_.insert(index);
      return true;
    }

    std::set<std::size_t> close() {
      std::lock_guard lock(mutex_);
      closed_ = true;
      return std::exchange(started_, {});
    }

  private:
    std::mutex mutex_;
    bool closed_ = false;
    std::set<std::size_t> started_;
  };

  enum class start_result { started, failed, gated };

  // Client setup and disconnect commands are independent lists, not pairs.
  // Preserve all disconnect commands (including undo-only configurations),
  // except when policy withheld setup and no setup command actually started.
  class client_session {
  public:
    template<class Spawn>
    bool start(Spawn &&spawn) {
      std::lock_guard lock(mutex_);
      if (closed_) return false;
      const auto result = spawn();
      gated_ |= result == start_result::gated;
      started_ |= result == start_result::started;
      return result == start_result::started;
    }

    bool close() {
      std::lock_guard lock(mutex_);
      if (closed_) return false;
      closed_ = true;
      return started_ || !gated_;
    }

  private:
    std::mutex mutex_;
    bool closed_ = false, started_ = false, gated_ = false;
  };
}
