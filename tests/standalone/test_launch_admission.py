"""Compile production replacement admission and account gate with effect counters."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[2]
s=(root/'src/nvhttp.cpp').read_text()
a=s.index('        if (\n          current_appid >',s.index('bool companion_replacement_admitted'))
b=s.index('        companion_replacement_admitted =',a)
admission=s[a:b]
a=s.index('#ifdef _WIN32\n        std::string companion_account;',b)
b=s.index('        if (companion_replacement_admitted)',a)
mutation=s[a:b]
prefix=r"""
#include <cassert>
#include <memory>
#include <optional>
#include <string>
#include <sstream>
#include <mutex>
#include "steam_account_policy.h"
std::ostringstream log_stream;
#define BOOST_LOG(x) log_stream
bool remote_active=false,prompt=false,mapped=true; int effects=0,admitted=0,account_checks=0;
struct Tree { template<class T> void put(const char*,const T&) {} } tree;
struct Identity {std::string uuid="synthetic";} request_client_identity;
namespace config {struct {bool remote_monitor_confirm_app_replacement=true;} video;}
namespace remote_session {
enum class app_replacement_confirmation_e {prompt, accepted};
void clear_app_replacement_confirmation(const std::string&){}
auto arm_or_confirm_app_replacement(const std::string&,int,int){return prompt?app_replacement_confirmation_e::prompt:app_replacement_confirmation_e::accepted;}
std::string app_replacement_confirmation_message(){return "fixture";}
}
struct Role {bool active;}; Role remote_role_gate_snapshot_for_client(const std::string&){return {remote_active};}
int active_session_generation(int){return 1;}
namespace proc {constexpr int input_only_app_id=99;struct P {
int active_session_guard(){return 1;}
bool check_companion_account(const std::string&,bool prepare,bool,const int*){++account_checks;if(prepare&&mapped)++effects;return true;}
} proc;}
namespace nvhttp {bool steam_mapping_for_client(const std::string&,std::string& a){a=mapped?"fixture":"";return mapped;}}
namespace audio {void acquire_startup_guard(std::shared_ptr<void>&){++effects;}}
void request(bool found=true) {
int current_appid=1,appid=2;std::string appuuid_str="b",current_app_uuid="a";
std::optional<int> requested_app=found?std::optional<int>(1):std::nullopt;bool joining_current=false;std::shared_ptr<void> companion_audio_guard;
"""
suffix=r"""
++admitted;
}
int main(){remote_active=true;request();assert(effects==0);
remote_active=false;prompt=true;request();assert(effects==0);
prompt=false;request(false);assert(effects==0);
request();assert(effects==2);
int before=effects,count=admitted,checks=account_checks;mapped=false;request();assert(admitted==count+1&&effects==before&&account_checks==checks+1);
remote_active=true;request();assert(admitted==count+1&&effects==before);}
"""
# Deferred path must derive its identity from retained session and lock before effects.
p=(root/'src/process.cpp').read_text();a=p.index('  int proc_t::launch_app_commands(');b=p.index('    // Some launchers disable',a);entry=p[a:b]
assert 'launch_mutex()' in entry and '_launch_session->client_uuid' in entry
assert 'companion_account_gate(companion_client, _env, false, false, nullptr, companion_recovery_ui(_app), companion_steam_app(_app))' in entry
assert entry.index('launch_mutex()')<entry.index('companion_account_gate(')
assert entry.index('auto fg = util::fail_guard')<entry.index('companion_account_gate(')
with tempfile.TemporaryDirectory(prefix='launch-admission-') as d:
    source=pathlib.Path(d)/'test.cpp';exe=pathlib.Path(d)/'test.exe'
    source.write_text(prefix+admission+mutation+suffix)
    subprocess.run([sys.argv[1],'-std=c++20','-D_WIN32','-iquote',str(root/'src'),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production admission: Remote Monitor, unconfirmed, missing replacements have zero effects; admitted replacement prepares PASS')
