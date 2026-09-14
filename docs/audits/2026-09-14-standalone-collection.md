# Standalone ISTAT collection

This checkpoint records the autonomous collector on 14 September 2026. It does
not attest completed collection or a new Hugging Face publication.

## Saved and verified code

- Publisher implementation: `b8d20544e26621c0b1d9cac0882451557239cce3`.
- Native retry implementation: `6a4ebd7dc209c59671f03579255baffcf32e215a`.
- Both implementations are pushed to their repositories' `plugin/opendata` branch.
- Publisher verification passes 20 focused tests: collection state and actual
  process/lock resumption, existing command ownership, and child environment.
- Native verification passes 154 tests in 82.37 seconds. Six existing CLI tests
  without the `no_live_models` marker are deselected; the two new public CLI
  policy-validation cases run and pass. No provider or model is contacted.
- Ruff and diff checks pass. The three native verification processes are gone,
  their process group is empty, and no owned retry database remains.

Evidence is retained in `build/collector-script-20260914/`, under
`publisher-verification/` and `native-verification/`. Private deployment inputs,
logs and collection state are ignored by Git.

## Current source work

Registry/report run 13 ends at `2026-09-14T01:24:46.033181Z` with explicit
`partial` status: 614 reports fetched, 10 failed, and one ambiguous relationship.
Its owner exits with status 1 and is reaped. The registry reconciliation and
successful individual reports remain committed. This result is not relabelled
as complete.

The standalone plan explicitly selects `structure` for ISTAT. It advances the
independent structure backlog using native database resumption; it does not
rerun or waive the incomplete metadata phase. Native run 14 starts at
`2026-09-14T05:45:08.776261Z`. Its first shared REST admission is recorded at
`2026-09-14T05:45:15.561704Z`; the shared gate advances by 13 seconds. These
observations establish startup and dispatch, not completed structure coverage.

`launchd` owns collector PID 44760, with parent PID 1, under
`gui/501/it.gramscii.open-data-catalogue.collection`. The recorded state is
`running`, step `structure`. It does not depend on a Codex command session.

## Bound inputs and operation

The persistent directory is `build/collector-script-20260914/` in this repository:

- `publisher/`: detached publisher source;
- `harvester/`: clean native source at the commit above;
- `private/collection.json`: plan, SHA-256
  `996bbfd7115adb0179ddde60958041eba608594b37eb977981bdfe1cf836b6a1`;
- `private/publisher.toml`, `collection.env`, and `retry.json`: bound deployment;
- `private/it.gramscii.open-data-catalogue.collection.plist`: loaded job definition;
- `collection/state.json`, `stdout.log`, and `stderr.log`: progress and failures.

The document contract is measured from the deployed source:
`2bbc2fe2f4a0f7684262c54e2cac536364ddf4d6bca2b0561aedc054d21d2c1e`.
The collection plan check and native document-policy readback pass without
provider requests. Quality thresholds remain unchanged.

The retry policy allows eight total attempts for a declared transient GET
failure, starting at 13 seconds with factor 2 and a 900-second backoff cap.
Provider Retry-After can extend that delay. A 429 without Retry-After defers the
shared gate for the explicitly configured 172800 seconds. These are operational
choices, not additional claimed official rate limits. Exhaustion stops with an
error; permanent failures do not enter a blind restart loop.

Inspect the active job and local state from this repository:

```sh
launchctl print gui/501/it.gramscii.open-data-catalogue.collection
cat build/collector-script-20260914/collection/state.json
tail -n 30 build/collector-script-20260914/collection/stderr.log
```

Closing Codex does not stop this launchd-owned job. The Mac must remain awake.
The job is loaded in the current login session; it is not installed for automatic
loading at a later login. After a reboot or logout, inspect the saved state and
native run, verify the declared inputs, then load the same plist explicitly:

```sh
python3 ./collect --plan build/collector-script-20260914/private/collection.json --check
launchctl bootstrap gui/501 "$PWD/build/collector-script-20260914/private/it.gramscii.open-data-catalogue.collection.plist"
```

An already loaded, stopped job can be started with `launchctl kickstart
gui/501/it.gramscii.open-data-catalogue.collection` after its failure is examined.
Do not kill a live collection or remove its kernel lock to start another writer.
The native Python environment still resides at
`/private/tmp/sdg-managed-composition-smoke-plan-20260911/python-env-v23`; retain
it while this deployment uses it. Missing inputs require an explicit rebuilt
deployment, not substitution of another environment.

Completion and failure have configured local macOS notification commands.
Notification visibility depends on macOS preferences; no future chat message is
scheduled. The collector invokes no Codex or language model and consumes no
Codex tokens. This does not publish the dataset or its README: unresolved source
rights, metadata, document regeneration and strict release verification remain
separate work.
