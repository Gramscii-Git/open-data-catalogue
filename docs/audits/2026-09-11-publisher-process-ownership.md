# Publisher process ownership and current core contracts

Code `95de83a99309e282eb255d764cad6dd8fd89021e` owns harvester, upload and offline
verification commands through a process-group supervisor and owner-lifetime
pipe. An interrupted or killed owner cannot leave those commands running.
An apparently successful command with live descendants is incomplete; the
supervisor terminates and reaps the group before release.

Publication and state locks use non-expiring OS locks. The supervisor inherits
the lock descriptors, so they remain held until command cleanup completes even
if the original owner dies. Lock files are not unlinked and OS unlock is not
issued ahead of the last owning descriptor. Existing directory locks are
explicit errors requiring operator reconciliation.

No total collection, upload, validation or readback cutoff is applied. A finite
shutdown grace is required external deployment policy and applies only after
termination. Source admission still uses original verification and expiry
clocks, actual completion time and the explicit scheduling reserve. Slow work
does not renew its evidence or turn an expired source into a current release.

## Configuration contracts

- Publisher configuration schema 2 requires `deployment.stop_grace_seconds`.
  Hub transport inactivity is explicit; the example declares `unbounded`.
- Update plan schema 3 requires cadence interval, expected run duration and
  minimum remaining validity. The expected duration is a scheduling forecast;
  it does not cancel work.
- Publisher scope schema 3 resolves to core BuildSpec schema 2. Required
  limits are validated before inventory access. Inventory transport inactivity
  is explicit; the example declares null.
- Offline provenance manifest schema 2 has no total work-timeout field.
  Availability archive contract 1 is unchanged.

Missing fields and obsolete schemas are rejected. Deployment configuration must
be updated together with the current core; no adapters or default values are
introduced.

All nine repository scopes pass static validation against actual core
`47790541fc9e93bf39fd673f530c4b1f9f0ba1f7`. The national scope uses the unchanged
retained 7,896-code inventory solely to validate structure. The check performs
no source request, archive build, publication or activation and changes no
source clock or TTL. This is not a fresh coverage qualification.

## Local verification

On macOS arm64 with the actual SDG Python 3.13 environment:

- Full unittest discovery: **162 passed in 36.210 seconds**.
- Focused ownership/readback tests: **8 passed in 3.187 seconds**, including
  actual owner SIGKILL, lock lifetime, incomplete descendant cleanup and later
  lock reuse.
- Ruff (`--isolated --target-version py313 catalogue tests`), compilation and
  `git diff --check`: passed.

The new owner-death test first reproduces the stale directory-lock failure;
that failed run is retained separately. Earlier checkpoint `1e93b97` passes
161 tests on both Python 3.14 and Python 3.13. The final additional lock change
is qualified on Python 3.13; another platform is not certified by this evidence.

The final source archive, tracked-file manifest, logs, prior checkpoint receipt
and cross-repository scope receipt are retained outside Git in
`build/publisher-process-ownership-20260911/`. Its receipt SHA-256 is
`f58da3ef585485c44b2e886a9e305ac7f621904c687d0bff93d92db9cf29e9f4`.

The updater is not installed by these tests. Discovery metadata/rights repair,
fresh source evidence, current publication admission, coordinated caller
adoption and a complete scheduled run remain separate release gates. Original
expired evidence is retained; no Hub data or README is republished by this
code qualification.
