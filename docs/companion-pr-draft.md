# Draft PR: Restore stream audio roles and integrate guarded companion launches

Streams can displace default audio endpoints, and deferred launch hooks can
outlive their owning session. Capture the original per-role audio baseline before
display changes, restore owned roles, and pair cleanup with executed hooks across
failure, reconnect and handover.

Add authenticated persistent client Steam assignments, remembered-account UI,
guarded helper calls and session-owned resolution preparation. All native tests
and implementation live in this repository; the companion runtime is separately
versioned. Account management and resolution automation are separate opt-ins under
Integrations, with retained assignments and explicit legacy migration. Keep this
PR draft until the new exact-head Windows build and independent review pass.

Validation: implementation commit 2d42271b82f9856365ad4a329cc3c023e8d9e824 has
exact staged tree 1c36f27021a00b389849888e615dd5c11f7c6655. Private native CI run
39079555905 passed production-source fixtures and Windows Release linking with
WebRTC/PyroWave; companion run 39079555897 passed offline checks. Repository-owned
CI and the eventual exact PR head require fresh validation. No live deployment,
Steam account changes or hardware acceptance tests are part of this publication.

See companion-source-control.md for pinned native consumption and CI requirements.

Local optional-integration validation: eight production-source native fixtures,
compiled migration policy check, 91 UI unit tests, production UI build, and seven
mocked production-preview browser cases passed. The unchanged companion passes
140 Python tests and its offline C# adapter/runtime suite. The actual configuration GTest suite (seven tests) also passes when compiled
with production config_steam.cpp, the pinned GoogleTest source and Zig. A full
Windows host build remains pending: this checkout has no CMake/Ninja/UCRT GCC,
populated native dependency submodules, Boost/FFmpeg SDKs or pinned WebRTC SDK.

No public native PR has yet been created. Publication remains pending the specific
approval for synthetic boundary test constants. No tests have been omitted.

Independent review found and prompted fixes for two cases: unavailable verification
must deny protected Steam launches without starting a helper, and resolution
preparation must never deny recovery video. Recovery preparation now runs only
through the deferred worker; regression fixtures cover both cases.
