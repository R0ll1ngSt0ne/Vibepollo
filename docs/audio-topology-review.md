# Pre-capture audio recovery checkpoint

Based on `309b9323625dceeff94f90f56a4c65abb09feb46`. This is an undeployed
development patch; no host audio, display, service, or game settings were tested.

## Changes

The shared audio context now releases its topology snapshot when capture never
assigned a sink, including failure before capture and audio-disabled sessions.
Windows observes render-role default and device-loss notifications from initial
snapshot until first sink assignment or final context release. A transition from
an observed unavailable endpoint preserves its preferred target and records the
exact fallback. A change from an available endpoint adopts the newer selection.
Missing notification evidence or failed registration also adopts current roles.
The original baseline therefore survives an observed topology fallback but does
not blindly replace a newer default selected before capture.

Topology-only recovery uses the existing per-role retry worker with its assignment
epoch and exact-current-endpoint checks. It never hides an endpoint and never
selects a fixed fallback. Late preferred endpoints and policy failures retry;
newer choices and successor epochs stop old writes. Failed initial sink assignments
retain pending topology recovery for only the failed roles. Existing transferred
recovery targets take precedence over the newer snapshot.

The base commit's guard handoff was re-reviewed: the active stream retains the
guard while waiting for the first audio ping and for audio-disabled streams;
the Web UI process path acquires it before creating its display. This patch does
not modify those source paths or account persistence.

## Validation and limits

`tests/unit/test_windows_audio_role_restore.py` compiles extracted production
notification, freeze, release, assignment, and recovery methods against deterministic
fake MMDevice/policy APIs. The native guard test executes the production acquisition
method with fake resource ownership, plus the guard-copy expressions. Source
assertions check the active-stream copy and the Web UI pre-display ordering.
These checks do not execute an HTTP server, real RTSP threads, COM registration,
or the actual display lifecycle. They supplement rather than replace host tests.

Validation completed: all 28 compiled replay cases passed (13 existing recovery
cases, 13 topology/notification cases, and 2 guard-lifetime cases). `git diff
--check` passed. Reproduce with Python and a C++23 compiler:

```
python tests/unit/test_windows_audio_role_restore.py src/platform/windows/audio.cpp --compiler PATH_TO_ZIG --zig
```

For GCC/Clang, omit `--zig` and supply the compiler executable directly. Use a
writable temporary directory and compiler cache; this runner never invokes live
Windows audio APIs.

Full host compilation is blocked in this environment: `cmake` is not on PATH,
Visual Studio installer discovery is absent at both standard Program Files paths,
and this isolated local clone has empty dependency submodules (including
`third-party/googletest` and `third-party/build-deps`). A locally supplied Zig
0.15.2 toolchain compiles and runs the fake-device replay. No dependencies were
downloaded or installed for this patch.

Windows default-device notifications contain no actor/provenance field. Observed
device loss is evidence of displacement, not proof that Windows rather than a
person selected the first fallback. A deliberate first choice made while the old
endpoint is unavailable can be indistinguishable from automatic fallback. A later
change while the fallback is available is preserved. Missing or reordered loss
notifications conservatively adopt the new default, potentially foregoing recovery.
If there is no nonempty current endpoint at final release, this patch does not
claim ownership of a later arbitrary endpoint. These cases require explicit
product policy or a trusted user-intent signal; do not describe this heuristic as
guaranteed manual-intent detection or deploy it without controlled validation.

Remaining host validation: callback ordering/lifetime and COM apartment behavior;
failure/cancel after actual topology mutation; actual Web UI and NVHTTP launches;
overlapping app replacement and final-owner cleanup; deliberate user changes
during device loss; no-current-endpoint cases; delayed HDMI/DP re-enumeration.

## Follow-up: synthetic Remote Monitor and stale enumeration

The follow-up delta is based on `2f14a738f8f7cd2c731ccac877b2f5d4d2119bd7`.
Synthetic Remote Monitor launch/resume acquires the shared audio guard before
`activate_or_resume_monitor`, whose runtime callbacks create displays and apply
topology. Accepted monitor ownership retains the guard even when startup is
retryable or transport is absent/audio-disabled. Rejected activation releases
the request guard; accepted activation preserves it until the monitor owner is
actually forgotten. Admission failure follows the existing display-release
result: a failed release retains ownership for retry. The RTSP/active stream
also holds its normal reference. Generation checks prevent stale cancellation
from releasing a successor. Owner removal, unpair, and shutdown release audio
references outside the owner-map mutex.

Enumeration now brackets its read with per-role notification revisions. Freeze
reconciles enumeration only for roles without a newer notification; a callback
received during enumeration wins, including its preferred manual selection.
The effective current-role array passed into assignment/recovery is updated to
that same observation. This addresses the reproducible F-to-M callback race;
it does not remove the first-fallback provenance ambiguity described above.

The expanded compiled replay passes 31 cases. New cases execute extracted native
owner-map lifecycle functions and inject a callback between enumeration and
freeze for assignment and cancellation. Source assertions verify capture before
synthetic Monitor activation and transfer into accepted owner state. Full HTTP,
Remote Monitor topology, and COM execution remain pending host validation.
