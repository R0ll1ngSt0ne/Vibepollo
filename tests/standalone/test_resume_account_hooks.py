"""Compile the production resume flow; execute its thread body deterministically."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'src/process.cpp').read_text()
a=source.index('  void proc_t::resume(');b=source.index('  void proc_t::pause(',a)
resume=source[a:b].replace('std::thread(', 'ImmediateThread(')
c=source.index('  bool proc_t::foreground_window_matches_running_app()',b)
pause=source[b:c].replace('std::thread(', 'ImmediateThread(')
stream=(root/'src/stream.cpp').read_text()
a=stream.index('      if (!session.do_cmds.empty()) {');b=stream.index('\n#if defined SUNSHINE_TRAY',a)
client_start=stream[a:b].replace('std::thread(', 'ImmediateThread(')
a=stream.index('      auto executed_hooks = session.hook_state->close();');b=stream.index('      // The app may already have exited',a)
client_stop=stream[a:b].replace('std::thread(', 'ImmediateThread(')
prefix=r'''
#include <cassert>
#include <map>
#include <memory>
#include <functional>
#include <future>
#include <list>
#include "hook_execution.h"
#include <mutex>
#include <sstream>
#include <string>
#include <system_error>
#include <vector>
#include "steam_account_policy.h"
using namespace std::literals;
std::ostringstream log_stream;
#define BOOST_LOG(x) log_stream
namespace bp {using environment=std::map<std::string,std::string>;}
namespace boost {namespace filesystem {using path=std::string;}}
int hooks=0,undos=0,videos=0,checks=0;bool correct=true;
struct ImmediateThread {template<class F> ImmediateThread(F f){f();}void detach(){}};
struct Child {
 void wait(){
   // The hook is still waiting, while a concurrent recovery launch acquires
   // the same policy mutex. The old implementation fails this assertion.
   auto recovery=std::async(std::launch::async,[]{std::unique_lock lock(steam_account_policy::launch_mutex(),std::try_to_lock);return lock.owns_lock();});
   assert(recovery.get());
 }
 void wait(std::error_code&){wait();}void detach(){}int exit_code(){return 0;}
};
namespace bp {using child=Child;}
namespace util {struct Guard {std::function<void()> f;~Guard(){if(f)f();}void disable(){f={};}};Guard fail_guard(std::function<void()> f){return {f};}}

namespace platf {
namespace bp=::bp;
void restore_screen_saver_state(){}
std::function<void()> deferred_screen_saver_restore(){return []{};}
void cache_screen_saver_state(){}
Child run_command(bool,bool,const std::string& cmd,const std::string&,bp::environment,void*,std::error_code&,void*){if(cmd=="synthetic-undo")++undos;else ++hooks;return {};}
}
std::string find_working_directory(const std::string&,const bp::environment&){return {};}
template<class T>bool companion_steam_app(const T&){return true;}
bool companion_account_gate(const std::string& client,bp::environment,bool prepare,bool identity,const char*,bool,bool){++checks;assert(!prepare&&identity&&client=="connecting-client");return correct;}
struct Command {std::string do_cmd="synthetic-game-launch",undo_cmd="synthetic-undo";bool elevated=false;};
struct proc_t {
  std::string _app_name="Steam Big Picture";
  std::shared_ptr<hook_execution::session> _state_hook_execution;
  std::shared_ptr<void> _companion_resolution_stop;
  struct {bool terminate_on_pause=false;std::string working_dir;std::vector<Command> state_cmds{Command{}};} _app;
  bp::environment _env;
  void start_companion_resolution(const std::string& client,int w,int h){assert(client=="connecting-client"&&w==2400&&h==1504);++videos;}
  void resume(const std::string&,int,int);
  void pause(bool);
  int current_app_id(){return 1;}int running(){return 1;}
  void terminate(bool,bool,bool,bool){assert(false);}
};
'''
client_prefix=r'''
namespace proc {
struct ClientHost {bp::environment get_env(){return {};}bool check_companion_hook(const std::string& client){assert(client=="connecting-client");return correct;}} proc;
std::string find_working_directory(const std::string&,const bp::environment&){return {};}
}
struct ClientCommand {std::string cmd;bool elevated=false;};
struct ClientSession {std::list<ClientCommand> do_cmds{{"synthetic-game-launch"}},undo_cmds{{"synthetic-undo"}};std::string device_uuid="connecting-client";std::shared_ptr<hook_execution::client_session> hook_state=std::make_shared<hook_execution::client_session>();};
'''
suffix=r'''
int main(){proc_t host;
host.resume("connecting-client",2400,1504);assert(videos==1&&hooks==1&&checks==1);host.pause(false);assert(undos==1);
// Disconnect, select another active account, then reconnect: video succeeds,
// but the automatic state hook cannot launch its synthetic game.
correct=false;host.resume("connecting-client",2400,1504);assert(videos==2&&hooks==1&&checks==2);host.pause(false);assert(undos==1);
correct=true;host.resume("connecting-client",2400,1504);assert(videos==3&&hooks==2&&checks==3);host.pause(false);assert(undos==2);
correct=false;ClientSession skipped;start_client(skipped);stop_client(skipped);assert(hooks==2&&undos==2);
correct=true;ClientSession ran;start_client(ran);stop_client(ran);assert(hooks==3&&undos==3);
stop_client(ran);assert(undos==3); // cleanup is consumed once
start_client(ran);assert(hooks==3); // a late detached worker cannot start after close
ClientSession unequal;unequal.undo_cmds.push_back({"synthetic-undo"});start_client(unequal);stop_client(unequal);assert(hooks==4&&undos==5);
ClientSession undo_only;undo_only.do_cmds.clear();stop_client(undo_only);assert(hooks==4&&undos==6);
correct=false;ClientSession gated_unequal;gated_unequal.undo_cmds.push_back({"synthetic-undo"});start_client(gated_unequal);stop_client(gated_unequal);assert(hooks==4&&undos==6);
// Pending replacement suppresses pause: the successor must retain prior work
// even when the successor's do command is withheld.
correct=true;host.resume("connecting-client",2400,1504);assert(hooks==5);
correct=false;host.resume("connecting-client",2400,1504);assert(hooks==5);
host.pause(false);assert(undos==7);host.pause(false);assert(undos==7);
// The parser also permits standalone application pause commands. They are
// explicit cleanup actions, not paired undo for a policy-withheld do command.
proc_t pause_only;pause_only._app.state_cmds[0].do_cmd.clear();pause_only.pause(false);assert(undos==8);

}
'''
with tempfile.TemporaryDirectory(prefix='resume-account-hooks-') as directory:
    path=pathlib.Path(directory);cpp=path/'test.cpp';exe=path/'test.exe';cpp.write_text(prefix+resume+pause+client_prefix+"void start_client(ClientSession &session){"+client_start+"}\nvoid stop_client(ClientSession &session){"+client_stop+"}\n"+suffix)
    subprocess.run([sys.argv[1],'-std=c++20','-D_WIN32','-iquote',str(root/'src'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production hook lifecycle: concurrent recovery during child wait; skipped do has no undo; independent client lists and undo-only cleanup; pending handover retains undo; closed session rejects late do PASS')
