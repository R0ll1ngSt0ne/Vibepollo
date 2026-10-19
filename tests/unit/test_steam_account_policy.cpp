#include "../tests_common.h"
#include <src/steam_account_policy.h>

TEST(SteamAccountAssignment, RejectsMalformedAndNonIndividualIds) {
  EXPECT_TRUE(steam_account_policy::valid_assignment(""));
  // Boundary fixtures only, not real household identities.
  EXPECT_TRUE(steam_account_policy::valid_assignment("76561197960265729"));
  EXPECT_TRUE(steam_account_policy::valid_assignment("76561202255233023"));
  EXPECT_FALSE(steam_account_policy::valid_assignment("76561197960265728"));
  EXPECT_FALSE(steam_account_policy::valid_assignment("76561202255233024"));
  EXPECT_FALSE(steam_account_policy::valid_assignment("account-name"));
  EXPECT_FALSE(steam_account_policy::valid_assignment("7656119796026572x"));
  EXPECT_FALSE(steam_account_policy::valid_assignment(" 76561197960265729"));
}
