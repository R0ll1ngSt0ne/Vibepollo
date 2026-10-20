#include "../../src/companion_integration_policy.h"
#include <cassert>
#include <initializer_list>
int main() {
 using namespace companion_integration_policy;
 assert(!account_enabled(false,false,false));
 assert(account_enabled(false,false,true));
 assert(!account_enabled(true,false,true));
 assert(account_enabled(true,true,false));
}
