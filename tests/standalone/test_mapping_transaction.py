"""Compile the actual mapping setter with deterministic persistence seams."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[2]
source = (root / 'src/nvhttp.cpp').read_text()
start = source.index('  bool steam_mapping_for_client(')
end = source.index('\n  bool set_client_hdr_profile(', start)
body = source[start:end]
prefix = r'''
#include <algorithm>
#include <cassert>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "steam_account_policy.h"
namespace crypto { struct named_cert_t { std::string uuid, steam_account_id; }; }
struct client_t { std::vector<std::shared_ptr<crypto::named_cert_t>> named_devices; };
client_t client_root;
std::mutex client_mutex, state_mutex, seam_mutex;
std::condition_variable seam_cv;
bool fail_write=false, block_write=false, entered=false, release_write=false;
std::string durable;
namespace config { namespace flag { enum { FRESH_STATE }; } struct { bool flags[1]{}; } sunshine; }
namespace statefile {
  void migrate_recent_state_keys() {}
  std::mutex &state_mutex() { return ::state_mutex; }
}
bool save_state_snapshot_locked(const client_t &staged) {
  std::unique_lock lock(seam_mutex);
  if(block_write) { entered=true; seam_cv.notify_all(); seam_cv.wait(lock,[]{return release_write;}); }
  if(fail_write) return false;
  durable=staged.named_devices[0]->steam_account_id;
  return true;
}
'''
suffix = r'''
int main() {
  const std::string a="76561197960265729", b="76561197960265730";
  std::string assignment="stale";
  assert(!steam_mapping_for_client("fixture",assignment) && assignment.empty());
  client_root.named_devices.push_back(std::make_shared<crypto::named_cert_t>(crypto::named_cert_t{"fixture", a}));
  assert(steam_mapping_for_client("fixture",assignment) && assignment==a);
  assert(!steam_mapping_for_client("unknown",assignment) && assignment.empty());
  assert(!steam_mapping_for_client("",assignment) && assignment.empty());
  client_root.named_devices.push_back(std::make_shared<crypto::named_cert_t>(crypto::named_cert_t{"empty", ""}));
  assert(!steam_mapping_for_client("empty",assignment) && assignment.empty());
  durable=a;
  fail_write=true;
  assert(!set_client_steam_account("fixture", b));
  assert(client_root.named_devices[0]->steam_account_id==a && durable==a);
  fail_write=false;
  assert(set_client_steam_account("fixture", b));
  assert(client_root.named_devices[0]->steam_account_id==b && durable==b);
  block_write=true;
  std::thread writer([&]{assert(set_client_steam_account("fixture", a));});
  {std::unique_lock lock(seam_mutex);seam_cv.wait(lock,[]{return entered;});}
  // Both state and client locks are held while persistence is suspended.
  assert(!client_mutex.try_lock()); assert(!state_mutex.try_lock());
  std::thread later([&]{assert(set_client_steam_account("fixture", b));});
  {std::lock_guard lock(seam_mutex);release_write=true;} seam_cv.notify_all();
  writer.join();later.join();
  assert(client_root.named_devices[0]->steam_account_id==b && durable==b);
  assert(!set_client_steam_account("missing", a));
  assert(!set_client_steam_account("fixture", "bad"));
  config::sunshine.flags[0]=true;
  assert(!set_client_steam_account("fixture", a));
}
'''
with tempfile.TemporaryDirectory(prefix='mapping-test-') as directory:
    test = pathlib.Path(directory) / 'test.cpp'
    exe = pathlib.Path(directory) / 'test.exe'
    test.write_text(prefix + body + suffix)
    subprocess.run([sys.argv[1], '-std=c++20', '-iquote', str(root/'src'), str(test), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=15)
print('Actual mapping setter: failed persistence, durable publication and concurrent serialization PASS')
