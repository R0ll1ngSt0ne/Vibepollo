#!/usr/bin/env python3
"""Compile production Windows role recovery against deterministic MMDevice/policy fakes."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('--compiler', default='/usr/bin/g++-15')
parser.add_argument('--sanitize', action='store_true')
parser.add_argument('--zig', action='store_true')
args = parser.parse_args()
source = args.source.read_text()

def function(signature, source=source):
    start = source.index(signature)
    body_start = start
    if '(' in signature:
        cursor = source.index('(', start) + 1
        parameters = 1
        while parameters:
            parameters += (source[cursor] == '(') - (source[cursor] == ')')
            cursor += 1
        body_start = cursor
    brace = source.index('{', body_start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

methods = '\n'.join(function(s) for s in (
    '    pending_role_restores_t freeze_topology_snapshot(',
    '    void restore_topology_snapshot() override',
    '    int set_sink(const std::string &sink) override',
    '    int restore_sink(const std::string &) override',
    '    static pending_role_restores_t normalize_pending_role_restores(',
    '    role_restore_result_e try_restore_pending_role(',
    '    reset_result_e try_reset_pending_roles_from_steam(',
    '    void run_pending_role_restore_task(',
)).replace(' override', '')
watcher = function('  class topology_notification_t:') + ';'
audio_source = (args.source.resolve().parents[2] / 'audio.cpp').read_text()
release = function('  void stop_audio_control(audio_ctx_t &ctx)', audio_source)
guard = function('  void acquire_startup_guard(', audio_source)
root = args.source.resolve().parents[3]
stream = (root / 'src/stream.cpp').read_text()
rtsp = (root / 'src/rtsp.cpp').read_text()
process = (root / 'src/process.cpp').read_text()
nvhttp = (root / 'src/nvhttp.cpp').read_text()
monitor_start = nvhttp.index('const bool is_remote_input = synthetic_control')
monitor_path = nvhttp[monitor_start:nvhttp.index('std::unique_lock normal_transition_lock', monitor_start)]
assert monitor_path.index('audio::acquire_startup_guard(') < monitor_path.index('remote_session::activate_or_resume_monitor(')
assert 'launch_session->role_generation,\n              launch_session->audio_startup_guard' in monitor_path
owner_struct = function('    struct remote_role_owner_t', nvhttp) + ';'
owner_methods = '\n'.join(function(sig, nvhttp) for sig in (
    '    std::string remote_role_owner_key(',
    '    void remember_remote_owner(',
    '    void forget_remote_owner(',
    '    void forget_remote_client(',
    '    void forget_all_remote_clients()',
))

# Source checks complement native ownership execution; they are not host tests.
assert 'session->audio_startup_guard = launch_session.audio_startup_guard;' in stream
assert 'snapshot->audio_startup_guard = audio_startup_guard;' in rtsp
assert process.index('audio::acquire_startup_guard(launch_session->audio_startup_guard)') < process.index('VDISPLAY::createVirtualDisplay(', process.index('int proc_t::execute('))

cpp = r'''
#include <algorithm>
#include <mutex>
#include <unordered_map>
#include "src/audio_topology_policy.h"
#include "src/audio_policy.h"
#include <array>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stop_token>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
using namespace std::literals;
using HRESULT = long;
using HANDLE = void *;
using DWORD = unsigned long;
using LPCWSTR = const wchar_t *;
#define STDMETHODCALLTYPE
enum EDataFlow { eRender, eCapture };
constexpr DWORD DEVICE_STATE_ACTIVE=1, DEVICE_STATE_NOTPRESENT=4;
constexpr HRESULT E_INVALIDARG=-2;
#define ERROR_NOT_FOUND 1
#define HRESULT_FROM_WIN32(x) (-3)
constexpr HRESULT S_OK = 0, E_FAIL = -1;
#define SUCCEEDED(x) ((x) >= 0)
#define FAILED(x) ((x) < 0)
#define BOOST_LOG(x) std::cerr
constexpr bool TRUE = true, FALSE = false;
HANDLE CreateEventW(void*, bool, bool, void*) { return reinterpret_cast<HANDLE>(1); }
void CloseHandle(HANDLE) {}
void SetEvent(HANDLE) {}
namespace util {
struct hex { HRESULT x; explicit hex(HRESULT v): x(v) {} std::string to_string_view() const { return std::to_string(x); } };
template<class F> struct guard { F f; ~guard() { f(); } };
template<class F> guard<F> fail_guard(F f) { return {f}; }
}
enum ERole { eConsole, eMultimedia, eCommunications, ERole_enum_count };
using role_device_ids_t = std::array<std::wstring, ERole_enum_count>;
struct pending_role_restore_t { ERole role; std::wstring preferred_id, expected_current_id; bool fallback_transition = false; };
using pending_role_restores_t = std::vector<pending_role_restore_t>;
using pending_restore_token_t = std::shared_ptr<std::atomic_bool>;
constexpr std::size_t role_index(ERole r) { return static_cast<std::size_t>(r); }
struct audio_notification_t {
 virtual ~audio_notification_t() = default;
 virtual HRESULT OnDeviceStateChanged(LPCWSTR, DWORD) { return S_OK; }
 virtual HRESULT OnDeviceRemoved(LPCWSTR) { return S_OK; }
 virtual HRESULT OnDefaultDeviceChanged(EDataFlow, ERole, LPCWSTR) { return S_OK; }
};
''' + watcher + r'''
struct pending_role_restore_handoff_t { std::uint64_t assignment_epoch=1; pending_role_restores_t role_restores; std::wstring steam_device_id; };
enum class role_restore_result_e { restored, no_longer_owned, inactive, no_device, failed };
enum class reset_result_e { success, inactive, no_device, fatal };
struct fixture_t {
 role_device_ids_t defaults {L"steam", L"steam", L"steam"};
 bool preferred_present = false, hide_fails = false, show_fails = false, marker_fails = false, shutdown = false;
 bool newer_owner = false, fail_restore_once = false;
 int hides = 0, shows = 0, writes = 0, waits = 0;
 int fail_assignment_role=-1; bool format_fails=false;
 std::function<void()> after_enumeration;
 pending_role_restores_t published;
 std::function<void()> on_wait;
 std::function<void()> on_show;
};
fixture_t *fixture;
namespace audio {
 struct wstring_t { std::wstring value; const wchar_t *get() const { return value.c_str(); } explicit operator bool() const { return !value.empty(); } };
}
struct device_t { std::wstring id; HRESULT GetId(audio::wstring_t *out) { out->value = id; return S_OK; } };
struct enumerator_t {
 template<class T> HRESULT RegisterEndpointNotificationCallback(T*) { return S_OK; }
 template<class T> HRESULT UnregisterEndpointNotificationCallback(T*) { return S_OK; }
};
using device_enum_t = std::shared_ptr<enumerator_t>;
std::shared_ptr<device_t> default_device(device_enum_t&, ERole role = eConsole) {
 const auto& id = fixture->defaults[role_index(role)];
 return id.empty() ? nullptr : std::make_shared<device_t>(device_t{id});
}
struct device_arrival_notification_t {
 explicit device_arrival_notification_t(const std::wstring&) {}
 bool wait(HANDLE, DWORD) {
  ++fixture->waits;
  if (fixture->waits > 3) throw std::runtime_error("worker did not finish after endpoint return");
  fixture->on_wait();
  return true;
 }
};
struct policy_t {
 HRESULT SetEndpointVisibility(const wchar_t*, bool visible) {
  if (visible) {
   ++fixture->shows;
   if (fixture->on_show) fixture->on_show();
   return fixture->show_fails ? E_FAIL : S_OK;
  }
  ++fixture->hides;
  if (fixture->hide_fails) return E_FAIL;
  for (auto& id: fixture->defaults) if (id == L"steam") id = L"controller";
  return S_OK;
 }
 HRESULT SetDefaultEndpoint(const wchar_t *id, ERole role) {
  if (std::wstring(id) == L"hdmi" && !fixture->preferred_present) return E_FAIL;
  if (fixture->fail_restore_once && std::wstring(id) == L"hdmi") { fixture->fail_restore_once = false; return E_FAIL; }
  fixture->defaults[role_index(role)] = id;
  ++fixture->writes;
  return S_OK;
 }
};
struct audio_control_t {
 topology_notification_t topology_notification;
 bool topology_registered=true, topology_frozen=false, topology_released=false;
 role_device_ids_t captured_default_device_ids;
 std::wstring assigned_device_id;
 std::string assigned_sink;
 pending_role_restore_handoff_t pending_role_restore_handoff;
 std::wstring worker_steam;
 role_device_ids_t current_default_device_ids() {
  auto ids=fixture->defaults;
  if(fixture->after_enumeration) { auto callback=std::move(fixture->after_enumeration); fixture->after_enumeration={}; callback(); }
  return ids;
 }
 std::optional<std::wstring> set_format(const std::string&) { return fixture->format_fails ? std::nullopt : std::make_optional(std::wstring(L"steam")); }
 pending_role_restore_handoff_t begin_policy_assignment(role_device_ids_t) {
  pending_role_restore_handoff_t value; value.role_restores=fixture->published; fixture->published.clear(); return value;
 }
 std::optional<HRESULT> set_default_endpoint_for_assignment(std::uint64_t, ERole role, const std::wstring& id) {
  if(fixture->newer_owner) return std::nullopt;
  if(role==fixture->fail_assignment_role && id==L"steam") return E_FAIL;
  return policy->SetDefaultEndpoint(id.c_str(),role);
 }
 static std::mutex& pending_restore_mutex_ref() { static std::mutex m; return m; }
 static std::uint64_t policy_assignment_epoch_ref() { return 1; }
 void start_pending_role_restore_task(const std::wstring& steam, pending_role_restores_t roles, std::uint64_t) {
  fixture->published=std::move(roles); worker_steam=steam;
 }
 device_enum_t device_enum = std::make_shared<enumerator_t>();
 std::shared_ptr<policy_t> policy = std::make_shared<policy_t>();
 bool pending_restore_worker_can_write(const std::stop_token& stop, const pending_restore_token_t& token, std::uint64_t) {
  return !stop.stop_requested() && token->load() && !fixture->newer_owner;
 }
 bool is_default_device(const std::wstring &id, ERole r) { return fixture->defaults[role_index(r)] == id; }
 bool adopt_current_policy_endpoint_for_worker(const pending_restore_token_t&, std::uint64_t, ERole) { return !fixture->newer_owner; }
 std::optional<std::wstring> preferred_device_match_list(const std::wstring& id) { return id; }
 std::optional<std::pair<int,std::wstring>> find_device_id(const std::wstring& id) {
  return fixture->preferred_present ? std::make_optional(std::make_pair(0,id)) : std::nullopt;
 }
 std::optional<HRESULT> set_default_endpoint_for_worker(const std::stop_token &stop, const pending_restore_token_t& token, std::uint64_t epoch, ERole role, const std::wstring &id) {
  if (!pending_restore_worker_can_write(stop, token, epoch)) return std::nullopt;
  return policy->SetDefaultEndpoint(id.c_str(),role);
 }
 bool process_shutdown_in_progress() { return fixture->shutdown; }
 bool write_visibility_marker(const std::wstring&) { return !fixture->marker_fails; }
 HRESULT show_steam_endpoint_with_retry(const std::wstring& id) { return policy->SetEndpointVisibility(id.c_str(),TRUE); }
 bool update_pending_role_restore_for_worker(const pending_role_restore_t& value, const pending_restore_token_t&, std::uint64_t, bool = true) {
  for (auto& pending: fixture->published) if (pending.role == value.role) { pending = value; return true; }
  return false;
 }
 void clear_pending_role_restore_for_worker(const pending_role_restore_t& value, const pending_restore_token_t&, std::uint64_t) {
  std::erase_if(fixture->published,[&](const auto& pending){ return pending.role == value.role; });
 }
 void clear_pending_role_restores_for_worker(const pending_role_restores_t&, const pending_restore_token_t&, std::uint64_t) { fixture->published.clear(); }
 void reassert_current_policy_assignment() {}
 void reassert_current_policy_assignment_role(ERole) {}
'''+methods+r'''
};
namespace lifecycle_probe {
 struct audio_ctx_t { bool restore_sink; audio_control_t *control; };
 bool retain_audio_control(audio_ctx_t&) { return false; }
 void restore_audio_control(audio_ctx_t& ctx) { ctx.control->restore_sink(""); }
''' + release + r'''
}
void check(bool value, const char *message) { if (!value) throw std::runtime_error(message); }
void run(const std::string &scenario) {
 fixture_t state;
 fixture = &state;
 audio_control_t control;
 auto token = std::make_shared<std::atomic_bool>(true);
 auto roles = pending_role_restores_t{{eConsole,L"hdmi",L"steam"},{eMultimedia,L"hdmi",L"steam"}};
 state.published = roles;
 state.on_wait = [&] {
  for (const auto& pending: state.published) {
   check(!pending.fallback_transition,"failed/finished visibility transition still owns arbitrary fallback");
   check(pending.expected_current_id==state.defaults[role_index(pending.role)],"published ownership lost exact fallback identity");
  }
  state.preferred_present = true;
 };
 if (scenario == "hide_failure") state.hide_fails = true;
 else if (scenario == "marker_failure") state.marker_fails = true;
 else if (scenario == "show_failure") state.show_fails = true;
 else if (scenario == "failed_fallback_user_choice") {
  state.show_fails = true;
  state.on_wait = [&] { state.defaults[eConsole]=L"user-speakers"; state.preferred_present=true; };
 }
 else if (scenario == "failed_show_user_choice") {
  state.show_fails = true;
  state.on_show = [&] { state.defaults[eConsole]=L"user-speakers"; };
  state.on_wait = [&] {
   check(state.published.size()==1 && state.published.front().role==eMultimedia,"retired console stopped surviving role recovery");
   check(state.published.front().expected_current_id==L"controller" && !state.published.front().fallback_transition,"surviving role lost exact fallback ownership");
   check(state.defaults[eConsole]==L"user-speakers","show failure replaced newer console choice");
   check(state.hides==1 && state.shows==1,"failed visibility fallback was retried");
   state.preferred_present=true;
  };
 }
 else if (scenario == "failed_fallback_new_owner") {
  state.hide_fails = true;
  state.on_wait = [&] { state.defaults[eConsole]=L"new-stream"; state.newer_owner=true; };
 }
 else if (scenario == "shutdown") state.shutdown = true;
 else if (scenario == "uncaptured") {
  state.marker_fails = true;
  for (auto& role: roles) role.preferred_id.clear();
  state.published = roles;
 }
 else if (scenario == "user_choice") state.on_wait = [&] { state.defaults[eConsole]=L"user-speakers"; state.preferred_present=true; };
 else if (scenario == "new_owner") state.on_wait = [&] { state.defaults[eConsole]=L"new-stream"; state.newer_owner=true; };
 else if (scenario == "restore_retry") { state.preferred_present=true; state.fail_restore_once=true; }
 else if (scenario == "handoff") {
  auto normalized = control.normalize_pending_role_restores(roles,L"steam",{L"controller",L"steam",L"user"});
  check(normalized.size()==1 && normalized.front().role==eMultimedia,"handoff adopted unowned role");
  roles.front().fallback_transition=true;
  normalized = control.normalize_pending_role_restores(roles,L"steam",{L"controller",L"steam",L"user"});
  check(normalized.size()==2 && normalized.front().preferred_id==L"hdmi" && normalized.front().expected_current_id==L"controller","handoff dropped published fallback transition");
  return;
 }
 control.run_pending_role_restore_task({},L"steam",roles,token,1);
 if (scenario == "shutdown" || scenario == "uncaptured") {
  check(state.writes==0 && state.published.empty(),"failed uncaptured/shutdown recovery was retained");
 }
 else if (scenario == "new_owner" || scenario == "failed_fallback_new_owner") check(state.defaults[eConsole]==L"new-stream","older worker overrode new owner");
 else {
  check(state.defaults[eConsole]==((scenario=="user_choice" || scenario=="failed_fallback_user_choice" || scenario=="failed_show_user_choice") ? L"user-speakers" : L"hdmi"),"preferred console endpoint not restored after return");
  check(state.defaults[eMultimedia]==L"hdmi","preferred multimedia endpoint not restored after return");
  check(state.defaults[eCommunications]==(state.hides && !state.hide_fails ? L"controller" : L"steam"),"uncaptured role was overwritten");
  check(state.published.empty(),"completed role recovery was not retired");
 }
}
namespace guard_probe {
 struct resource {};
 using audio_ctx_ref_t = std::shared_ptr<resource>;
 std::weak_ptr<resource> shared;
 audio_ctx_ref_t get_audio_ctx_ref() { auto ref=shared.lock(); if(!ref) { ref=std::make_shared<resource>(); shared=ref; } return ref; }
''' + guard + r'''
 struct launch {
  std::shared_ptr<void> audio_startup_guard;
  std::shared_ptr<launch> clone() {
   auto snapshot=std::make_shared<launch>();
   snapshot->audio_startup_guard = audio_startup_guard;
   return snapshot;
  }
 };
 void run(bool disabled) {
  auto source=std::make_shared<launch>();
  acquire_startup_guard(source->audio_startup_guard);
  auto first=source->audio_startup_guard;
  acquire_startup_guard(source->audio_startup_guard);
  check(first==source->audio_startup_guard,"guard acquisition not idempotent"); first.reset();
  auto startup=source->clone();
  auto session=std::make_shared<launch>();
  auto &launch_session=*startup;
  session->audio_startup_guard = launch_session.audio_startup_guard;
  source.reset(); startup.reset();
  check(!shared.expired(),"snapshot lost before delayed audio ping");
  auto capture=disabled ? audio_ctx_ref_t{} : get_audio_ctx_ref();
  session.reset();
  check(disabled ? shared.expired() : !shared.expired(),"wrong audio-disabled/capture ownership");
  capture.reset(); check(shared.expired(),"final owner leaked snapshot");
 }
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
void topology_run(const std::string &scenario) {
 fixture_t state; fixture=&state;
 state.defaults={L"hdmi",L"speakers",L"headset"};
 audio_control_t control;
 control.captured_default_device_ids=state.defaults;
 control.topology_notification.capture(state.defaults);
 // Notifications are injected into the production observer, not a model clone.
 if(scenario!="unexplained_change") control.topology_notification.OnDeviceStateChanged(L"hdmi",DEVICE_STATE_NOTPRESENT);
 state.defaults[eConsole]=L"fallback";
 if(scenario!="late_notification") control.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"fallback");
 if(scenario=="registration_failure") control.topology_registered=false;
 if(scenario=="manual_before_assignment" || scenario=="manual_before_cancel") {
  state.defaults[eConsole]=L"manual";
  control.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"manual");
 }
 if(scenario=="freeze_race_assignment" || scenario=="freeze_race_cancel") {
  state.after_enumeration=[&] {
   state.defaults[eConsole]=L"manual";
   control.topology_notification.OnDefaultDeviceChanged(eRender,eConsole,L"manual");
  };
 }
 if(scenario=="manual_before_assignment" || scenario=="freeze_race_assignment") {
  check(control.set_sink("stream")==0,"sink assignment failed");
  check(control.captured_default_device_ids[eConsole]==L"manual","manual selection not adopted");
  state.preferred_present=true;
  control.restore_sink("");
  check(state.defaults[eConsole]==L"manual","manual baseline overwritten");
  return;
 }
 if(scenario=="partial_assignment") {
  state.fail_assignment_role=eConsole;
  check(control.set_sink("stream")!=0,"partial failure not reported");
  check(state.published.size()==1,"failed topology role lost");
 } else {
  if(scenario=="format_failure") { state.format_fails=true; check(control.set_sink("stream")!=0,"format failure lost"); control.restore_sink(""); }
  else { lifecycle_probe::audio_ctx_t ctx{false,&control}; lifecycle_probe::stop_audio_control(ctx); }
 }
 if(scenario=="manual_before_cancel" || scenario=="unexplained_change" || scenario=="registration_failure" || scenario=="late_notification" || scenario=="freeze_race_cancel") { check(state.published.empty(),"manual choice claimed"); return; }
 check(state.published.size()==1,"topology displacement lost");
 check(state.published.front().expected_current_id==L"fallback","wrong fallback ownership");
 state.on_wait=[&] { state.preferred_present=true; if(scenario=="manual_after_cancel") state.defaults[eConsole]=L"manual"; if(scenario=="successor") { state.newer_owner=true; state.defaults[eConsole]=L"successor"; } };
 if(scenario=="cancel") { auto pending=state.published; control.restore_topology_snapshot(); check(state.published.size()==pending.size(),"double release lost recovery"); }
 if(scenario=="late_endpoint") state.on_wait=[&] { if(state.waits>=2) state.preferred_present=true; };
 auto token=std::make_shared<std::atomic_bool>(true);
 control.run_pending_role_restore_task({},control.worker_steam,state.published,token,1);
 check(state.hides==0 && state.shows==0,"topology recovery changed visibility");
 check(state.defaults[eConsole]==(scenario=="manual_after_cancel" ? L"manual" : scenario=="successor" ? L"successor" : L"hdmi"),"topology recovery endpoint wrong");
 check(state.defaults[eCommunications]==(scenario=="partial_assignment" ? L"steam" : L"headset"),"unowned role overwritten");
}
int main() {
 int failed=0;
 try { monitor_probe::run(); std::cout<<"remote_monitor_retained_lifecycle: PASS\n"; }
 catch(const std::exception &e) { ++failed; std::cout<<"remote_monitor: FAIL: "<<e.what()<<"\n"; }
 try { guard_probe::run(false); std::cout<<"delayed_audio_ping: PASS\n"; guard_probe::run(true); std::cout<<"disabled_guard_release: PASS\n"; }
 catch(const std::exception &e) { ++failed; std::cout<<"guard: FAIL: "<<e.what()<<"\n"; }
 for (const std::string scenario : {"normal_return","hide_failure","marker_failure","show_failure","user_choice","new_owner","restore_retry","handoff","failed_fallback_user_choice","failed_show_user_choice","failed_fallback_new_owner","shutdown","uncaptured"}) {
  try { run(scenario); std::cout<<scenario<<": PASS\n"; }
  catch (const std::exception &e) { ++failed; std::cout<<scenario<<": FAIL: "<<e.what()<<"\n"; }
 }
 for(const std::string scenario : {"failed_launch", "cancel", "format_failure", "audio_disabled", "late_endpoint", "manual_before_assignment", "manual_before_cancel", "manual_after_cancel", "successor", "partial_assignment", "unexplained_change", "registration_failure", "late_notification", "freeze_race_assignment", "freeze_race_cancel"}) {
  try { topology_run(scenario); std::cout<<scenario<<": PASS\n"; }
  catch(const std::exception &e) { ++failed; std::cout<<scenario<<": FAIL: "<<e.what()<<"\n"; }
 }
 return failed ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory(prefix='audio-470-replay-') as temp:
    directory=Path(temp)
    unit=directory/'production.cpp'
    binary=directory/'production.exe'
    unit.write_text(cpp)
    flags=['-std=c++23','-O2','-g','-pthread','-Wall','-Wextra']
    if args.sanitize: flags += ['-fsanitize=address,undefined','-fno-omit-frame-pointer']
    subprocess.run([args.compiler, *(['c++'] if args.zig else []), *flags, '-I', str(args.source.resolve().parents[3]), str(unit),'-o',str(binary)],check=True)
    result=subprocess.run([str(binary)],check=False)
    raise SystemExit(result.returncode)
