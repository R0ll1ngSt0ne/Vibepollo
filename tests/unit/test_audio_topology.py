"""Exercise production Windows topology notifications and role assignment against fake endpoints."""
from pathlib import Path
import subprocess, sys, tempfile
root = Path(__file__).resolve().parents[2]
source = (root / 'src/platform/windows/audio.cpp').read_text()
def extract(signature, source=source):
    begin = source.index(signature)
    body = begin
    if '(' in signature:
        cursor = source.index('(', begin) + 1
        parameters = 1
        while parameters:
            parameters += (source[cursor] == '(') - (source[cursor] == ')')
            cursor += 1
        body = cursor
    brace = source.index('{', body)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end].replace(' override', '')
watcher = extract('  class topology_notification_t:') + ';'
methods = '\n'.join(extract(s) for s in ('    pending_role_restores_t freeze_topology_snapshot(', '    void restore_topology_snapshot() override', '    int set_sink(const std::string &sink) override', '    int restore_sink(const std::string &) override'))
nvhttp = (root / 'src/nvhttp.cpp').read_text()
owner_struct = extract('    struct remote_role_owner_t', nvhttp) + ';'
owner_methods = '\n'.join(extract(sig, nvhttp) for sig in (
    '    std::string remote_role_owner_key(', '    void remember_remote_owner(',
    '    void forget_remote_owner(', '    void forget_remote_client(', '    void forget_all_remote_clients()',
))
program = r'''
#include "src/audio_role_control.h"
#include "src/audio_topology_policy.h"
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
using HRESULT = long;
using DWORD = unsigned long;
using LPCWSTR = const wchar_t *;
#define STDMETHODCALLTYPE
constexpr HRESULT S_OK=0;
constexpr DWORD DEVICE_STATE_ACTIVE=1, DEVICE_STATE_NOTPRESENT=4;
enum EDataFlow { eRender, eCapture };
enum ERole { eConsole, eMultimedia, eCommunications, ERole_enum_count };
using role_policy_t = audio::role_control_t<ERole,3>;
using role_device_ids_t = role_policy_t::ids_t;
using pending_role_restores_t = role_policy_t::pending_list_t;
constexpr std::size_t role_index(ERole role) { return static_cast<std::size_t>(role); }
struct audio_notification_t {};
''' + watcher + r'''
void check(bool ok, const char *message) { if (!ok) throw std::runtime_error(message); }
struct fixture_t {
 role_device_ids_t defaults {L"dp",L"speakers",L"headset"};
 role_policy_t::registry_t registry;
 pending_role_restores_t scheduled;
 std::wstring scheduled_steam;
 std::uint64_t epoch=0;
 bool format_failure=false;
 int fail_role=-1;
 std::function<void()> during_read;
 role_device_ids_t read() {
  auto result=defaults;
  if(during_read) { auto f=std::move(during_read); during_read={}; f(); }
  return result;
 }
 role_policy_t::device_api_t devices() {
  return {[this]{return read();},[this](ERole role,const std::wstring &id)->long {
   if(role==fail_role && id==L"stream")return -1;
   defaults[role]=id;return 0;
  },[](const std::wstring &id){return std::optional<std::wstring>(id);},[](std::jthread){},
  [this](const std::wstring &steam,pending_role_restores_t roles,std::uint64_t generation){ scheduled_steam=steam;scheduled=std::move(roles);epoch=generation;},[](std::uint64_t){},{}};
 }
};
struct control_t {
 fixture_t &f;
 role_policy_t roles_;
 topology_notification_t topology_notification;
 bool topology_registered=true,topology_frozen=false,topology_released=false;
 std::string assigned_sink;
 explicit control_t(fixture_t &value):f(value),roles_(f.registry,f.devices()) {roles_.capture(f.defaults);topology_notification.capture(f.defaults);}
 auto &pending_restore_mutex_ref(){return f.registry.mutex;}
 auto policy_assignment_epoch_ref(){return f.registry.epoch;}
 auto current_default_device_ids(){return f.read();}
 auto set_format(const std::string&){return f.format_failure ? std::optional<std::wstring>{} : std::make_optional(std::wstring(L"stream"));}
 auto begin_policy_assignment(role_device_ids_t ids){auto [h,t]=f.registry.begin(std::move(ids));return h;}
 auto normalize_pending_role_restores(pending_role_restores_t p,const std::wstring &s,const role_device_ids_t &ids){return role_policy_t::normalize(std::move(p),s,ids);}
 void start_pending_role_restore_task(const std::wstring &steam,pending_role_restores_t p,std::uint64_t epoch){f.scheduled=std::move(p);f.scheduled_steam=steam;f.epoch=epoch;}
''' + methods + r'''
};
void run(const std::string &scenario) {
 fixture_t f;control_t c(f);
 if(scenario!="unexplained")c.topology_notification.OnDeviceStateChanged(L"dp",DEVICE_STATE_NOTPRESENT);
 f.defaults[eConsole]=L"fallback";
 c.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"fallback");
 if(scenario=="registration_failure")c.topology_registered=false;
 if(scenario=="manual" || scenario=="manual_assignment") {
  f.defaults[eConsole]=L"user";c.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"user");
 }
 if(scenario=="race")f.during_read=[&]{f.defaults[eConsole]=L"user";c.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"user");};
 if(scenario=="assignment" || scenario=="manual_assignment") {
  check(c.set_sink("stream")==0,"assignment failed");
  c.restore_sink("");
  check(f.defaults[eConsole]==(scenario=="assignment"?L"dp":L"user"),"wrong restored baseline");
  check(f.defaults[eMultimedia]==L"speakers" && f.defaults[eCommunications]==L"headset","roles mixed");return;
 }
 if(scenario=="partial") {f.fail_role=eConsole;check(c.set_sink("stream")!=0,"partial failure missing");}
 else {
  if(scenario=="format_failure") {f.format_failure=true;check(c.set_sink("stream")!=0,"format failure missing");}
  c.restore_topology_snapshot();
 }
 if(scenario=="manual" || scenario=="race" || scenario=="unexplained" || scenario=="registration_failure") {check(f.scheduled.empty(),"unowned default claimed");return;}
 check(f.scheduled.size()==1,"missing topology recovery");
 check(f.scheduled[0].preferred_id==L"dp" && f.scheduled[0].expected_current_id==L"fallback","wrong recovery ownership");
 check(f.scheduled_steam.empty(),"topology recovery must not hide Steam endpoints");
 if(scenario!="partial") {auto epoch=f.epoch;c.restore_topology_snapshot();check(f.epoch==epoch,"double release scheduled again");}
}
namespace monitor_probe {
 namespace remote_session {
  enum class role_e { none, monitor, input };
  void clear_app_replacement_confirmation(std::string_view) {}
 }
''' + owner_struct + r'''
 std::mutex remote_role_owners_mutex;
 std::unordered_map<std::string,remote_role_owner_t> remote_role_owners;
''' + owner_methods + r'''
 void run() {
  int releases=0;
  auto guard=std::shared_ptr<void>(new int(1),[&](void *p) {
   check(remote_role_owners_mutex.try_lock(),"audio released under owner-map lock");
   remote_role_owners_mutex.unlock(); delete static_cast<int*>(p); ++releases;
  });
  std::weak_ptr<void> weak=guard;
  remember_remote_owner("client",remote_session::role_e::monitor,1,guard);
  // Failed/retryable startup, audio-disabled transport, and transport loss:
  // request/capture references leave; retained monitor still owns topology.
  guard.reset(); check(!weak.expired(),"retained monitor lost audio baseline");
  auto resumed=weak.lock();
  remember_remote_owner("client",remote_session::role_e::monitor,2,resumed);
  resumed.reset(); forget_remote_owner("client",remote_session::role_e::monitor,1);
  check(!weak.expired(),"stale cancel released successor");
  forget_remote_owner("client",remote_session::role_e::monitor,2);
  check(weak.expired() && releases==1,"explicit release did not retire monitor baseline");
  auto unpaired=std::make_shared<int>(2); weak=unpaired;
  remember_remote_owner("client",remote_session::role_e::monitor,3,unpaired);
  unpaired.reset(); forget_remote_client("client"); check(weak.expired(),"unpair leaked guard");
  auto shutdown=std::make_shared<int>(3); weak=shutdown;
  remember_remote_owner("client",remote_session::role_e::monitor,4,shutdown);
  shutdown.reset(); forget_all_remote_clients(); check(weak.expired(),"shutdown leaked guard");
 }
}
int main(){monitor_probe::run();int failures=0;for(const auto &s:{"cancel","format_failure","partial","assignment","manual_assignment","manual","race","unexplained","registration_failure"})try{run(s);std::cout<<s<<": PASS\n";}catch(const std::exception &e){++failures;std::cerr<<s<<": "<<e.what()<<'\n';}return failures!=0;}
'''
with tempfile.TemporaryDirectory(prefix='audio-topology-') as folder:
    unit=Path(folder)/'test.cpp';binary=Path(folder)/'test.exe';unit.write_text(program)
    subprocess.run([sys.argv[1],'-std=c++23','-pthread','-Wall','-Wextra','-Werror','-I',str(root),str(unit),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
