"""Compile the real prep iterator declarations with the production policy skip."""
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
#include <sstream>
#include <string>
#include <vector>
std::ostringstream log_stream;
#define BOOST_LOG(x) log_stream
struct cmd_t {std::string do_cmd="setup",undo_cmd="cleanup";};
bool allowed=false,recovery=true;
bool companion_account_gate(const std::string&,int,bool,bool,const char*,bool,bool){return allowed;}
template<class T>bool companion_steam_app(const T&){return true;}
template<class T>bool companion_recovery_ui(const T&){return recovery;}
struct Host {
 struct {std::vector<cmd_t> prep_cmds{cmd_t{}};} _app;
 int _env=0,spawned=0;std::string companion_client="synthetic-client";
'''
body=r'''
 int prepare(){
 _app_prep_begin=_app.prep_cmds.begin();_app_prep_it=_app_prep_begin;
 for(;_app_prep_it!=_app.prep_cmds.end();++_app_prep_it){
 auto &cmd=*_app_prep_it;
'''
suffix=r'''
 ++spawned;
 }return 0;}
};
int main(){
 Host skipped;assert(skipped.prepare()==0&&skipped.spawned==0&&skipped._app.prep_cmds[0].undo_cmd.empty());
 allowed=true;Host ran;assert(ran.prepare()==0&&ran.spawned==1&&ran._app.prep_cmds[0].undo_cmd=="cleanup");
 allowed=false;recovery=false;Host game;assert(game.prepare()==403&&game.spawned==0);
}
'''
with tempfile.TemporaryDirectory(prefix='prep-hook-cleanup-') as directory:
    path=pathlib.Path(directory);cpp=path/'test.cpp';exe=path/'test.exe'
    cpp.write_text(prefix+declarations+body+gate+suffix)
    subprocess.run([sys.argv[1],'-std=c++20',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production prep iterator and gate: recovery skip has no setup or undo; admitted hook keeps cleanup; game denial retained PASS')
