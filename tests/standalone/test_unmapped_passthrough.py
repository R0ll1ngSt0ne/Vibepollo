"""Compile the production account gate and mapping lookup with counted effects."""
import pathlib,subprocess,sys,tempfile
root=pathlib.Path(__file__).resolve().parents[2]
s=(root/'src/process.cpp').read_text();a=s.index('    bool companion_recovery_ui(');b=s.index('    bool companion_config_gate(',a);gate=s[a:b]
a=s.index('  bool proc_t::check_companion_account(');b=s.index('  int proc_t::execute(',a);admission=s[a:b]
s=(root/'src/nvhttp.cpp').read_text();a=s.index('  bool steam_mapping_for_client(');b=s.index('  bool set_client_steam_account(',a);lookup=s[a:b]
prefix=r'''
#include <cassert>
#include <chrono>
#include <future>
#include <algorithm>
#include <cstdio>
#include <array>
#include <filesystem>
#include <map>
#include <memory>
#include <mutex>
#include <regex>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>
#include "steam_account_policy.h"
std::ostringstream sink;
#define BOOST_LOG(x) sink
namespace bp {using environment=std::map<std::string,std::string>;}
namespace boost {namespace filesystem {using path=std::filesystem::path;}}
using DWORD=unsigned long;
int exit_status=0;int helper_calls=0,module_calls=0;std::string selected,command_seen;
std::filesystem::path executable;
struct Prep {std::string do_cmd;};
struct ctx_t {std::string playnite_id,lutris_id,lutris_directory,steam_install_dir,steam_id,cmd;bool playnite_fullscreen=false;std::vector<std::string> state_cmds,detached;std::vector<Prep> prep_cmds;};
struct proc_t {bp::environment _env;bool check_companion_account(const std::string&,bool,bool,const ctx_t* = nullptr) const;};
bool accounts_enabled=true,runtime_available=true;
bool companion_accounts_enabled(){return accounts_enabled;}
bool companion_runtime_available(){return runtime_available;}
bool companion_steam_app(const ctx_t& app){return !app.steam_id.empty()&&app.playnite_id.empty()&&!app.playnite_fullscreen&&app.lutris_id.empty();}
struct unsupported_proc_t : proc_t {bool check_companion_account(const std::string&,bool,bool,const ctx_t* = nullptr) const;};
DWORD GetModuleFileNameW(void*,wchar_t* out,DWORD size){++module_calls;auto s=executable.wstring();assert(s.size()<size);std::copy(s.begin(),s.end(),out);return s.size();}
using HANDLE=void*;
constexpr DWORD SYNCHRONIZE=0x100000,PROCESS_TERMINATE=1,WAIT_OBJECT_0=0,WAIT_TIMEOUT=258,WAIT_FAILED=0xffffffff;
constexpr bool FALSE=false;
namespace util {template<class F>struct Guard{F f;~Guard(){f();}};template<class F>Guard<F> fail_guard(F f){return {f};}}
bool simulate_timeout=false,termination_fails=false,open_fails=false,wait_fails=false,signaled=false;
int terminations=0,detachments=0,exit_reads=0,closes=0,collections=0;
std::vector<long long> waits;
HANDLE const own_helper=reinterpret_cast<HANDLE>(123);
HANDLE OpenProcess(DWORD access,bool inherit,DWORD pid){assert(access==(SYNCHRONIZE|PROCESS_TERMINATE)&&!inherit&&pid==42);signaled=false;return open_fails?nullptr:own_helper;}
void CloseHandle(HANDLE h){assert(h==own_helper);++closes;}
DWORD WaitForSingleObject(HANDLE h,DWORD duration){
 assert(h==own_helper);waits.push_back(duration);
 if(duration==30000&&(simulate_timeout||wait_fails))return wait_fails?WAIT_FAILED:WAIT_TIMEOUT;
 if(duration==2000&&termination_fails)return WAIT_TIMEOUT;
 signaled=true;return WAIT_OBJECT_0;
}
bool TerminateProcess(HANDLE h,unsigned code){assert(h==own_helper&&code==1);++terminations;return !termination_fails;}
struct Child {
 DWORD id(){return 42;}
 void wait(){assert(signaled);++collections;}
 void detach(){++detachments;}
 int exit_code(){assert(signaled);++exit_reads;return exit_status;}
};
namespace platf {namespace dxgi {std::string wide_to_utf8(const std::wstring& s){return std::string(s.begin(),s.end());}}
Child run_command(bool,bool interactive,const std::string& command,const std::filesystem::path&,bp::environment env,void* output,std::error_code&,void*){assert(!interactive&&output);std::fputs("{\"status\":\"account_ready\"}\n",static_cast<FILE*>(output));++helper_calls;selected=env["VIBEPOLLO_COMPANION_STEAM_ID"];command_seen=command;return {};}}
namespace nvhttp {
struct Client {std::string uuid,steam_account_id;};
struct {std::vector<std::shared_ptr<Client>> named_devices;} client_root;
std::mutex client_mutex;
'''
suffix=r'''
int main(int argc,char** argv){executable=std::filesystem::path(argv[1])/"sunshine.exe";
using nvhttp::client_root;using nvhttp::Client;
client_root.named_devices.push_back(std::make_shared<Client>(Client{"mapped","76561197960265729"}));
client_root.named_devices.push_back(std::make_shared<Client>(Client{"empty",""}));
for(auto id:{"missing","empty",""})for(bool prepare:{false,true})for(bool identity:{false,true}){
assert(companion_account_gate(id,{},prepare,identity));assert(helper_calls==0&&module_calls==0);
}
assert(client_root.named_devices[0]->steam_account_id=="76561197960265729");assert(client_root.named_devices[1]->steam_account_id.empty());
assert(companion_account_gate("mapped",{},true));assert(helper_calls==1&&selected=="76561197960265729");assert(command_seen.ends_with("prepare-env"));
assert(sink.str().find("Companion result: account_ready")!=std::string::npos);
assert(companion_account_gate("empty",{},false,false,"current-config-env"));assert(helper_calls==2&&selected.empty());assert(command_seen.ends_with("current-config-env"));
exit_status=10;assert(companion_account_gate("empty",{},false,false,"current-config-env"));
exit_status=4;assert(!companion_account_gate("empty",{},false,false,"current-config-env"));
assert(companion_account_gate("empty",{},true));
ctx_t desktop,ui;ui.detached={"steam://open/bigpicture"};
assert(companion_recovery_ui(desktop)&&companion_recovery_ui(ui));
auto game=ui;game.steam_id="fixture-game";assert(!companion_recovery_ui(game));
auto custom=desktop;custom.cmd="fixture-command";assert(!companion_recovery_ui(custom));
custom=desktop;custom.prep_cmds.push_back({"fixture-housekeeping"});assert(companion_recovery_ui(custom));
custom.state_cmds.push_back("fixture-resume-hook");assert(companion_recovery_ui(custom));
custom=ui;custom.detached.push_back("fixture-game");assert(!companion_recovery_ui(custom));
const auto before=helper_calls;
for(auto state:{"stopped","updating","login-needed","wrong-account","remembered-target"}) {
  (void)state; // Recovery admission deliberately does not depend on Steam state.
  assert(companion_account_gate("mapped",{},true,false,nullptr,true));
  assert(companion_account_gate("mapped",{},false,false,nullptr,true));
}
assert(helper_calls==before); // No updater interference, account switch, or delay.
{ // A stalled verifier holds the account lock on another thread; bypass still returns.
 std::promise<void> acquired,release;auto released=release.get_future();
 auto blocked=std::async(std::launch::async,[&]{std::lock_guard lock(steam_account_policy::launch_mutex());acquired.set_value();released.wait();});
 acquired.get_future().wait();
 auto recovery=std::async(std::launch::async,[&]{return companion_account_gate("mapped",{},true,false,nullptr,true,false);});
 const bool prompt=recovery.wait_for(std::chrono::seconds(1))==std::future_status::ready;
 auto protected_launch=std::async(std::launch::async,[&]{return companion_account_gate("mapped",{},true);});
 const bool rejected_promptly=protected_launch.wait_for(std::chrono::seconds(1))==std::future_status::ready;
 release.set_value();blocked.get();assert(prompt&&recovery.get());
 assert(rejected_promptly&&!protected_launch.get());
 assert(helper_calls==before); // Contention must not select an account or start a helper.
}

proc_t process;
assert(process.check_companion_account("mapped",true,false,&ui));
assert(process.check_companion_account("mapped",false,true,&game));
assert(helper_calls==before); // HTTP preflight and resume cannot reintroduce 403.
assert(!process.check_companion_account("mapped",true,false,&game));
assert(!companion_account_gate("mapped",{},false)); // Automatic game launch still blocked.
const auto calls_before_bypass=helper_calls;
for(bool enabled:{false,true})for(bool available:{false,true})for(bool managed:{false,true}) {
 accounts_enabled=enabled;runtime_available=available;
 if(enabled&&available&&managed)continue;
 assert(companion_account_gate("mapped",{},true,false,nullptr,false,managed)==(!enabled||!managed));
 assert(helper_calls==calls_before_bypass);
}
accounts_enabled=false;runtime_available=true;exit_status=0;
assert(companion_account_gate("mapped",{},false,false,"current-config-env"));
assert(selected.empty()); // Disabled management ignores the retained assignment for independent resolution.
const auto calls_after_optional=helper_calls;
accounts_enabled=true;runtime_available=true;
assert(process.check_companion_account("mapped",true,false,&desktop));
assert(process.check_companion_account("mapped",true,false,&custom));
assert(helper_calls==calls_after_optional);
unsupported_proc_t unsupported;exit_status=4;
assert(unsupported.check_companion_account("mapped",true,false,&game));
assert(helper_calls==calls_after_optional);
// Execute the real timeout branches without sleeping or terminating any process.
// A nominal success exit code must not turn a timed-out helper into admission.
exit_status=0;simulate_timeout=true;
for(bool failed:{false,true}) {
 termination_fails=failed;waits.clear();terminations=detachments=exit_reads=closes=collections=0;
 const auto previous_calls=helper_calls;
 assert(!companion_account_gate("mapped",{},true));
 assert(helper_calls==previous_calls+1);
 assert((waits==std::vector<long long>{30000,2000}));
 assert(terminations==1&&detachments==(failed?1:0)&&exit_reads==0&&closes==1&&collections==(failed?0:1));
 // Timeout releases the policy lock even when its own helper cannot terminate.
 auto unlocked=std::async(std::launch::async,[]{std::unique_lock lock(steam_account_policy::launch_mutex(),std::try_to_lock);return lock.owns_lock();});
 assert(unlocked.get());
 assert(companion_account_gate("mapped",{},true,false,nullptr,true,false));
 assert(helper_calls==previous_calls+1); // Recovery starts no replacement helper.
}
simulate_timeout=false;termination_fails=false;
assert(companion_account_gate("mapped",{},true)); // A later verified attempt can recover.
open_fails=true;waits.clear();terminations=detachments=closes=collections=exit_reads=0;
assert(!companion_account_gate("mapped",{},true));
assert(waits.empty()&&terminations==0&&detachments==1&&closes==0&&collections==0&&exit_reads==0);
open_fails=false;wait_fails=true;waits.clear();terminations=detachments=closes=collections=exit_reads=0;
assert(!companion_account_gate("mapped",{},true));
assert((waits==std::vector<long long>{30000,2000}));
assert(terminations==1&&detachments==0&&closes==1&&collections==1&&exit_reads==0);
wait_fails=false;
assert(companion_account_gate("mapped",{},true));
}
'''
with tempfile.TemporaryDirectory(prefix='unmapped-passthrough-') as d:
 path=pathlib.Path(d);helper=path/'stream-companion'/'StreamCompanion.Windows.exe';helper.parent.mkdir();helper.write_bytes(b'fixture')
 cpp=path/'test.cpp';exe=path/'test.exe';cpp.write_text(prefix+lookup+'}\n'+gate+admission+'\n#undef _WIN32\n'+admission.replace('proc_t::','unsupported_proc_t::')+'\n#define _WIN32\n'+suffix)
 subprocess.run([sys.argv[1],'-std=c++20','-iquote',str(root/'src'),str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe),str(path)],check=True,timeout=15)
print('Production unmapped account gate: admission succeeds with zero helper effects; mapped target retained; current config never selects; contention fails fast; timeout/failed termination deny and release lock PASS')
