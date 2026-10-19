"""Exercise production STARTUPINFO handle allowlisting with disposable child processes."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(__file__).resolve().parents[2]
s=(root/'src/platform/windows/misc.cpp').read_text()
a=s.index('  STARTUPINFOEXW create_startup_info(');b=s.index('\n  }',a)+4
startup=s[a:b]
prefix=r'''
#include <windows.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <io.h>
#include <string>
#include <system_error>
LPPROC_THREAD_ATTRIBUTE_LIST allocate_proc_thread_attr_list(DWORD count){
 SIZE_T bytes=0;InitializeProcThreadAttributeList(nullptr,count,0,&bytes);
 auto list=static_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(std::malloc(bytes));
 if(!InitializeProcThreadAttributeList(list,count,0,&bytes)){std::free(list);return nullptr;}return list;
}
'''
suffix=r'''
int main(int argc,char** argv){
 if(argc==2){
   auto parent=reinterpret_cast<HANDLE>(std::stoull(argv[1]));
   assert(WaitForSingleObject(parent,0)==WAIT_TIMEOUT);
   DWORD code=0;assert(!GetExitCodeProcess(parent,&code)); // no query permission
   assert(GetLastError()==ERROR_ACCESS_DENIED);
   CloseHandle(parent);return 0;
 }
 HANDLE parent=nullptr;
 assert(DuplicateHandle(GetCurrentProcess(),GetCurrentProcess(),GetCurrentProcess(),&parent,SYNCHRONIZE,TRUE,0));
 std::error_code ec;auto startup=create_startup_info(nullptr,nullptr,ec,&parent);assert(!ec);
 wchar_t executable[32768];assert(GetModuleFileNameW(nullptr,executable,32768));
 std::wstring command=L"\""+std::wstring(executable)+L"\" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(parent));
 PROCESS_INFORMATION child{};
 assert(CreateProcessW(nullptr,command.data(),nullptr,nullptr,TRUE,EXTENDED_STARTUPINFO_PRESENT|CREATE_NO_WINDOW,nullptr,nullptr,&startup.StartupInfo,&child));
 CloseHandle(parent);CloseHandle(child.hThread);
 assert(WaitForSingleObject(child.hProcess,10000)==WAIT_OBJECT_0);
 DWORD code=1;assert(GetExitCodeProcess(child.hProcess,&code)&&code==0);CloseHandle(child.hProcess);
 DeleteProcThreadAttributeList(startup.lpAttributeList);std::free(startup.lpAttributeList);
}
'''
with tempfile.TemporaryDirectory(prefix='resolution-lifetime-') as directory:
    path=pathlib.Path(directory);cpp=path/'test.cpp';exe=path/'test.exe';cpp.write_text(prefix+startup+suffix)
    subprocess.run([sys.argv[1],'-std=c++20',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=15)
print('Production lifetime handle: child inherits SYNCHRONIZE-only handle without host ACL changes PASS')
