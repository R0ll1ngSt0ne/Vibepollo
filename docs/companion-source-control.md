# Native source ownership and release consumption

All native C++, Web UI integration, native tests and related documentation belong
in this Vibepollo branch. The draft PR targets R0ll1ngSt0ne/Vibepollo, not upstream.
The private companion PR is not a substitute. Publication is pending approval of
synthetic identifier boundary fixtures; retain the complete tests without
obfuscating or rerouting them to bypass the publication review.

## Pinned consumption

After publication, add native-source.json to the companion with the repository,
full final native commit SHA, full tree SHA and reviewed native CI run. Replace
the private native-host.yml clone/apply step with a credential-free checkout of
R0ll1ngSt0ne/Vibepollo at that commit. Verify HEAD and HEAD^{tree} against the
lock before submodules/build. Never use a moving branch or fall back to patches.
Trigger integration builds when the lock or runtime changes. Record native
commit/tree and companion commit/tree separately in artifact provenance.

The private build can compile that checkout and combine its runtime, or consume
native artifacts with verified commit/tree provenance. Existing patches become
a recovery archive, not editable source or active release inputs. Keep archive
integrity checks; remove reconstruction from the active path only after the first
successful pinned build. Preserve staged deployment/rollback manifests unchanged.
Do not activate a lock to an unpublished commit that CI cannot fetch.

## Native CI plan

companion-regressions.yml runs native policy checks, eight production-source
fixtures, fake-device audio replay, Web UI unit tests and production UI build
from this checkout, without Steam or secrets. The workflow also runs the mocked production-preview mapping cases with
playwright.companion.config.ts.

Before merge, run the existing Windows pipeline on the exact native head with
Release, WebRTC/PyroWave and the audio, RTSP startup snapshot and account-policy
GTests. Inspect required reusable-workflow inputs before dispatch. Do not invoke
signing, releases or installation as a compile shortcut. Preserve commit/tree
provenance and logs. Previous private CI validates the implementation tree, not
the new workflow or future PR merge tree. Builds do not establish live behavior.

## Completion criteria

1. Complete native branch published and draft PR created, with every test retained.
2. Exact-head native CI passes and public content contains no real local identity
   data, credentials or pairing material.
3. Companion consumes the pinned native commit and passes integration CI without
   applying patches as its source reconstruction path.
4. Archive and staged rollback remain recoverable. Installation remains separate
   and waits for optional-Steam design changes and a user-scheduled idle window.

## Optional Steam policy and migration

`steam_account_management` and `steam_resolution_automation` are independent of
`steam_enabled` catalog discovery. New installs default both to off. If the
account-management key is absent but saved assignments exist, only explicit
Steam-managed app launches retain account protection; the UI marks migration
pending until an administrator explicitly saves on/off. Existing mappings are
never removed by migration, missing Steam, unsupported platform, or disabling.
Resolution automation does not inherit a legacy enabled state.

Ordinary Desktop, Big Picture recovery and other launchers do not perform account
selection or gate generic hooks. Steam scope requires Steam app metadata and no
alternate launcher metadata. Windows runtime/Steam executable presence is a
capability check, not authenticated-account readiness. Unsupported/absent runtime
paths perform no helper calls. Applicable protected Steam launches fail closed
when their verifier is unavailable; generic and recovery access still pass. All
recovery-UI resolution preparation is deferred and cannot deny video.
Account readiness remains enforced by the helper
only for applicable enabled mapped launches. Resolution has its own opt-in and
safety checks and can use the observed account when management is off.

Changing these options during an active stream is persisted but deferred through
the existing host reload mechanism; the UI reports deferred application. This
avoids leaving a running resolution worker under a changed policy. Installation
and mapping changes on the real host are not part of this source migration.
