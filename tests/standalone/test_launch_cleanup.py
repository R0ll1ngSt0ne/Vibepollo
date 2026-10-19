"""Compile the actual command-entry guard with synthetic lifecycle ownership."""
import pathlib,subprocess,sys,tempfile
root=pathlib.Path(__file__).resolve().parents[2]
s=(root/'src/process.cpp').read_text();a=s.index('  int proc_t::launch_app_commands(');b=s.index('    // Some launchers disable',a);b=s.rfind('#ifdef _WIN32',a,b)
entry=s[a:b]
prefix=r"""
#include <cassert>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <system_error>
#include <thread>
#include <atomic>
#include "steam_account_policy.h"
namespace util {template<class F> struct Guard {F f;~Guard(){f();}};template<class F> auto fail_guard(F f){return Guard<F>{f};}}
bool ready=false;std::atomic<int> observations=0;
bool companion_account_gate(const std::string& client,int,bool,bool,const char*,bool recovery,bool){assert(!recovery);++observations;return ready&&client=="owner";}
template<class T> bool companion_steam_app(const T&){return true;}
template<class T> bool companion_recovery_ui(const T&){return false;}
struct Session {std::string client_uuid="owner";};
struct proc_t {
int app_id=7,_env=0;bool audio=true,display=true,deferred=false;
std::shared_ptr<Session> _launch_session=std::make_shared<Session>();
struct {std::vector<int> prep_cmds;} _app;
std::vector<int>::iterator _app_prep_begin,_app_prep_it;
void terminate(bool,bool,bool,bool,bool){app_id=0;_launch_session.reset();audio=display=false;}
int launch_app_commands(bool,bool);
};
"""
suffix=r"""
return 0;}
void cleared(const proc_t& p){assert(p.app_id==0&&!p._launch_session&&!p.audio&&!p.display);}
int main(){proc_t immediate;assert(immediate.launch_app_commands(true,true)==403);cleared(immediate);
proc_t deferred;deferred.deferred=true;deferred.deferred=false;assert(deferred.launch_app_commands(true,false)==403);cleared(deferred);
// Account/mapping transition owns the same lock. Deferred verification cannot
// observe the former identity while a transition is still in progress.
proc_t raced;std::unique_lock gate(steam_account_policy::launch_mutex());int before=observations;
std::atomic<bool> launched=false;std::thread worker([&]{launched=true;assert(raced.launch_app_commands(true,false)==403);});
while(!launched.load())std::this_thread::yield();assert(observations==before);
ready=false;gate.unlock();worker.join();cleared(raced);assert(observations==before+1);
}
"""
with tempfile.TemporaryDirectory(prefix='launch-cleanup-') as d:
    cpp=pathlib.Path(d)/'test.cpp';exe=pathlib.Path(d)/'test.exe';cpp.write_text(prefix+entry+suffix)
    subprocess.run([sys.argv[1],'-std=c++20','-D_WIN32','-iquote',str(root/'src'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production entry cleanup: immediate/deferred rejection releases app, session, audio/display; deferred identity serialization PASS')
