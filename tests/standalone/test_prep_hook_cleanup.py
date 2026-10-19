"""Compile the real prep iterator declarations with production denial and completed-prefix cleanup."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[2]
header=(root/'src/process.h').read_text()
declarations='\n'.join(line for line in header.splitlines() if 'iterator _app_prep_' in line)
assert declarations.count(';')==2
source=(root/'src/process.cpp').read_text()
start=source.index('      if (!companion_account_gate(companion_client, _env, false, true, nullptr, false, companion_steam_app(_app))) {')
end=source.index('\n#endif',start)
gate=source[start:end]
prefix=r'''
#include <cassert>
#include "prep_command_lifetime.h"
#include <sstream>
#include <string>
#include <vector>
std::ostringstream log_stream;
#define BOOST_LOG(x) log_stream
struct cmd_t {std::string do_cmd="setup",undo_cmd="cleanup";};
bool allowed=false;
bool companion_account_gate(const std::string&,int,bool,bool,const char*,bool,bool){return allowed;}
template<class T>bool companion_steam_app(const T&){return true;}
struct Host {
 struct {std::vector<cmd_t> prep_cmds{cmd_t{}};} _app;
 int _env=0,spawned=0,undone=0;std::string companion_client="synthetic-client";
'''
body=r'''
 int prepare(){
 _app_prep_begin=_app.prep_cmds.begin();_app_prep_it=_app_prep_begin;
 int prep_failure=-1;
 bool completed=proc::command_lifetime::prepare(_app_prep_it,_app.prep_cmds.cend(),[&](const auto &cmd){
'''
suffix=r'''
 ++spawned;
 return true;});return completed?0:prep_failure;}
 void cleanup(){proc::command_lifetime::undo(_app_prep_it,_app_prep_begin,[&](const auto&){++undone;});}
};
int main(){
 Host denied;assert(denied.prepare()==403&&denied.spawned==0);denied.cleanup();assert(denied.undone==0);
 assert(denied._app.prep_cmds[0].undo_cmd=="cleanup"); // Rejection does not mutate app configuration.
 allowed=true;Host ran;assert(ran.prepare()==0&&ran.spawned==1);ran.cleanup();assert(ran.undone==1);ran.cleanup();assert(ran.undone==1);
 allowed=false;Host undo_only;undo_only._app.prep_cmds[0].do_cmd.clear();assert(undo_only.prepare()==0);undo_only.cleanup();assert(undo_only.undone==1);
}
'''
with tempfile.TemporaryDirectory(prefix='prep-hook-cleanup-') as directory:
    path=pathlib.Path(directory);cpp=path/'test.cpp';exe=path/'test.exe'
    cpp.write_text(prefix+declarations+body+gate+suffix)
    subprocess.run([sys.argv[1],'-std=c++20','-iquote',str(root/'src'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production prep iterator and gate: protected denial has no setup or undo; successful and undo-only hooks clean up once PASS')
