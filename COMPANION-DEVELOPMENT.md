# Streaming companion integration (draft, not deployed)

Native source of truth: this repository, branch `companion/integration`.
Base: `66e169c325dab73e4e780fe34ac3c613af4cdf52`.
The 25 implementation commits through `2d42271b82f9856365ad4a329cc3c023e8d9e824`
produce tree `1c36f27021a00b389849888e615dd5c11f7c6655`, exactly matching the
reviewed staged candidate. Later CI/docs commits do not change that implementation.
Original history, GPL license and NOTICE are retained.

This repository owns native audio role restoration and topology ownership,
client assignment persistence and authenticated UI, helper invocation and worker
lifetime, launch admission, and hook cleanup across reconnect/handover. Native
regressions live in tests/standalone, tests/unit and the Web UI test directories.
The separate companion owns its C# runtime, adapters and deployment tooling.

The branch now separates optional account management and resolution automation
from catalog discovery. Integrations owns assignments; generic Desktop and other
launcher paths bypass Steam account work. Legacy assignments are retained with
an explicit migration notice. These changes supersede the staged candidate and
require fresh exact-head Windows build/review before installation.

Private native run 39079555905 passed seven production-source fixtures and linked
Release with WebRTC/PyroWave for the exact implementation tree. Companion run
39079555897 passed offline checks. Live audio, account recovery and game behavior
remain unverified. New native CI must run after publication; it has not run on
GitHub. See docs/companion-source-control.md for CI and source migration.

Publication does not authorize deployment. Preserve staged binaries and rollback
manifests. Never commit pairings, local account/client identifiers, credentials,
or machine inventory. Do not change live Steam/configuration as a test shortcut.
