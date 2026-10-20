"""Compile production adapter dispatch with synthetic app/session metadata."""
import pathlib,subprocess,sys,tempfile
root=pathlib.Path(__file__).resolve().parents[2];s=(root/'src/process.cpp').read_text();a=s.index('    bool companion_config_gate(');b=s.index('\n#endif',a);body=s[a:b]
prefix=r"""
#include <cassert>
#include <algorithm>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <vector>
std::ostringstream log_stream;
#define BOOST_LOG(x) log_stream
namespace bp {using environment=std::map<std::string,std::string>;}
struct Prep {std::string do_cmd;};
struct ctx_t {std::string steam_id,cmd,steam_install_dir,playnite_id,lutris_id,lutris_directory;bool playnite_fullscreen=false;std::vector<std::string> detached;std::vector<Prep> prep_cmds,state_cmds;};
namespace rtsp_stream {struct launch_session_t {int width=2560,height=1440;std::string virtual_display_device_id="fixture-display";std::optional<std::string> output_name_override;};}
namespace config {struct {std::string output_name;} video;struct {bool resolution_automation=true;} steam;}
bool companion_accounts_enabled(){return true;}
bool available=true;
bool companion_runtime_available(){return available;}
template<class T>bool companion_steam_app(const T& app){return !app.steam_id.empty()&&app.playnite_id.empty()&&!app.playnite_fullscreen&&app.lutris_id.empty();}
template<class T>bool companion_recovery_ui(const T& app){return app.steam_id.empty()&&app.cmd.empty()&&app.playnite_id.empty()&&!app.playnite_fullscreen&&app.lutris_id.empty();}
bool mapped=true,helper_ready=true;
namespace nvhttp {bool steam_mapping_for_client(const std::string&,std::string& account){account=mapped?"fixture":"";return mapped;}}
namespace VDISPLAY {std::optional<std::string> resolveUsableDisplayName(const std::string&){return "fixture-gdi";}}
std::string operation;int calls=0;
bool companion_account_gate(const std::string&,bp::environment e,bool,bool,const char* op){++calls;operation=op;assert(e["VIBEPOLLO_COMPANION_WIDTH"]=="2560");assert(e["VIBEPOLLO_COMPANION_DISPLAY"]=="fixture-gdi");return helper_ready;}
"""
suffix=r"""
int main(){rtsp_stream::launch_session_t session;ctx_t desktop;
assert(companion_config_gate("fixture",{},desktop,session)&&calls==0);
ctx_t big;big.detached={"steam://open/bigpicture"};assert(companion_config_gate("fixture",{},big,session)&&calls==0);
helper_ready=false;assert(companion_config_gate("fixture",{},big,session)&&calls==0);helper_ready=true;
ctx_t nms;nms.steam_id="275850";nms.steam_install_dir="fixture";assert(companion_config_gate("fixture",{},nms,session)&&operation=="config-env");
ctx_t pal;pal.steam_id="1623730";pal.steam_install_dir="fixture";assert(companion_config_gate("fixture",{},pal,session)&&operation=="config-env");
int before=calls;nms.detached={"arbitrary"};assert(!companion_config_gate("fixture",{},nms,session)&&calls==before);
ctx_t other;other.steam_id="42";assert(companion_config_gate("fixture",{},other,session)&&calls==before);
ctx_t custom;custom.cmd="arbitrary";assert(companion_config_gate("fixture",{},custom,session)&&calls==before);
ctx_t playnite;playnite.playnite_id="fixture-game";assert(companion_config_gate("fixture",{},playnite,session)&&calls==before);
ctx_t fullscreen;fullscreen.playnite_fullscreen=true;assert(companion_config_gate("fixture",{},fullscreen,session)&&calls==before);
ctx_t lutris;lutris.lutris_id="fixture-game";assert(companion_config_gate("fixture",{},lutris,session)&&calls==before);
ctx_t prep;prep.prep_cmds.push_back({"launcher"});assert(companion_config_gate("fixture",{},prep,session)&&calls==before);
ctx_t state;state.state_cmds.push_back({"launcher"});assert(companion_config_gate("fixture",{},state,session)&&calls==before);
mapped=false;before=calls;helper_ready=false;
assert(companion_config_gate("fixture",{},desktop,session)&&calls==before);
assert(companion_config_gate("fixture",{},big,session)&&calls==before);helper_ready=true;
assert(companion_config_gate("fixture",{},pal,session)&&operation=="current-config-env");
helper_ready=false;assert(!companion_config_gate("fixture",{},pal,session));
mapped=true;assert(!companion_config_gate("fixture",{},pal,session));helper_ready=true;before=calls;
big.playnite_fullscreen=true;assert(companion_config_gate("fixture",{},big,session)&&calls==before);
config::steam.resolution_automation=false;
assert(companion_config_gate("fixture",{},pal,session)&&calls==before);
config::steam.resolution_automation=true;available=false;
assert(companion_config_gate("fixture",{},pal,session)&&calls==before);
available=true;pal.playnite_id="other-launcher";
assert(companion_config_gate("fixture",{},pal,session)&&calls==before);
}
"""
with tempfile.TemporaryDirectory(prefix='config-routing-') as d:
 cpp=pathlib.Path(d)/'test.cpp';exe=pathlib.Path(d)/'test.exe';cpp.write_text(prefix+body+suffix)
 subprocess.run([sys.argv[1],'-std=c++20','-iquote',str(root/'src'),str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=15)
print('Production routing: Desktop, stock Big Picture, direct NMS, unsupported apps and detached rejection PASS')
