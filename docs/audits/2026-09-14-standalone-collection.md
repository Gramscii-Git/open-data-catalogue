# Standalone ISTAT collection

This checkpoint records the autonomous collector on 14 September 2026. It does
not attest completed collection or a new Hugging Face publication.

## Saved and verified code

- Publisher implementation: `b8d20544e26621c0b1d9cac0882451557239cce3`, on
  `main` through `0a8edea7f178a1688ce7459517f4e50134ce9471`, which adds only
  documentation to it.
- Native retry implementation: `6a4ebd7dc209c59671f03579255baffcf32e215a`, on
  SDG `main`.
- Publisher verification passes 20 focused tests: collection state and actual
  process/lock resumption, existing command ownership, and child environment.
- Native verification passes 154 tests in 82.37 seconds. Six existing CLI tests
  without the `no_live_models` marker are deselected; the two new public CLI
  policy-validation cases run and pass. No provider or model is contacted.
- Ruff and diff checks pass. The three native verification processes are gone,
  their process group is empty, and no owned retry database remains.
- The running native source is SDG `64b2263d3c8d21895fd05b4cd8621b68ea9cff06`.
  It carries three structure-harvest changes, each verified in its pull request:
  a dataset whose provider answers keep failing is recorded and the harvest
  continues ([PR 159](https://github.com/Gramscii-Git/semantic-deterministic-graph/pull/159)),
  a sync honours a stop before its metadata reports
  ([PR 160](https://github.com/Gramscii-Git/semantic-deterministic-graph/pull/160)),
  and datasets with a stored error are harvested after the others while ISTAT's
  "doesn't contain a mapping set" answer is recorded without retries
  ([PR 161](https://github.com/Gramscii-Git/semantic-deterministic-graph/pull/161)).
  Its one later runtime change declares the same answer permanent for OECD in
  `providers.yaml` ([PR 164](https://github.com/Gramscii-Git/semantic-deterministic-graph/pull/164));
  the ISTAT collection code is that of `9f502ea6`.
- The running publisher is `628c311694ffca08bb09de90b89523ae5586428d`. A
  collection plan declares `patience_seconds`, which the collector passes to the
  structure step as `--patience`
  ([PR 14](https://github.com/Gramscii-Git/open-data-catalogue/pull/14)).

Evidence for the first two implementations is retained in
`build/collector-script-20260914/`, under `publisher-verification/` and
`native-verification/`. Private deployment inputs, logs and collection state
are ignored by Git.

## Current source work

Registry/report run 13 ends at `2026-09-14T01:24:46.033181Z` with explicit
`partial` status: 614 reports fetched, 10 failed, and one ambiguous relationship.
Its owner exits with status 1 and is reaped. The registry reconciliation and
successful individual reports remain committed. This result is not relabelled
as complete.

The standalone plan explicitly selects `structure` for ISTAT. It advances the
independent structure backlog using native database resumption; it does not
rerun or waive the incomplete metadata phase. These runs have advanced it:

| Run | Deployment | Native source | Start | End |
| --- | --- | --- | --- | --- |
| 14 | `build/collector-script-20260914/` | `6a4ebd7d` | `2026-09-14T05:45:08.776261Z` | `08:36:10.676116Z`, `error`: eight attempts on dataflow `115_362` exhausted |
| 15 | `build/collector-script-20260914-r2/` | `54feded5` | `09:38:00.281125Z` | `11:36:29.305254Z`, `error`: `interrupted by a server restart` |
| 16 | `build/collector-script-20260914-r3/` | `9f502ea6` | `11:37:10.98585Z` | `13:58:47.396637Z`, `error`: stopped after one request waited 88 minutes |
| 17 | `build/collector-script-20260914-r3/` | `9f502ea6` | `13:59:36.123805Z` | `14:20:14.761074Z`, `error`: stopped while retrying the same dataflow |
| 18 | one dataset, from the r3 harvester | `9f502ea6` | `14:20:40.927808Z` | `14:30:40.991637Z`, `error`: selected refresh without a structure |
| 19 | `build/collector-script-20260914-r4/` | `64b2263d` | `14:32:49.380513Z` | running |

ISTAT answers every request for `115_362` with HTTP 500 and the body
`Dataflow 'urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=IT1:115_362(1.0)'
doesn't contain a mapping set`. Run 15 recorded that answer on the dataflow and
wrote the four base-year dataflows under it before the machine restarted; its
last ISTAT admission is at `10:23:16Z` and the machine boots again at
`10:23:45Z`. The restart removed `/private/tmp`, which held the interpreter both
earlier deployments ran on. Run 15 was then closed with the plugin's
`service.close_interrupted`, and run 16 started from a rebuilt deployment. By
`11:47:34.851767Z` run 16 has written 24 structures without error, beginning with
`117_1035` rather than the recorded `115_362`. These observations establish
startup and dispatch, not completed structure coverage.

From `12:30Z` run 16 waited 88 minutes on one request, for
`123_712_DF_DCAR_INDBILPER_1`. Its harvester was stopped with SIGTERM; once no
collection process or database client remained, the run was closed with
`service.close_interrupted` and the job was started again. Run 17 asked for the
same dataflow at `13:59:41Z` and received HTTP 500 after nine and a half
minutes. No rule declares that answer permanent, so the retry policy scheduled
another attempt; eight attempts of that length would hold the collection for
about two hours on one dataflow. Run 17 was stopped and closed the same way.

Run 18 harvested only that dataflow with `--patience 600`, from the r3
harvester, with logs in `build/patience-20260914/`. It stored the structure
error `no answer within 600s` and ended `error`, because a selected refresh
replaces vocabulary only after a successful exact structure. Run 19 takes the
whole ISTAT backlog from r4, whose plan passes the same patience. A dataset left
without an answer keeps its error and is harvested after the others by the next
run.

The patience is measured. Between `10:20Z` and `12:30Z`, 101 intervals between
consecutive ISTAT structure writes have a median of 26 seconds and a 95th
percentile of 41 seconds. The longest inside a run are 387 seconds before
`122_54` and 206 seconds before `122_54_DF_DCSC_TUR_1`; the 4,481 seconds before
`117_1035` span the restart between runs 15 and 16.

`launchd` owns the collection under
`gui/501/it.gramscii.open-data-catalogue.collection`. It does not depend on a
Codex or Claude session.

## Bound inputs and operation

The persistent directory is `build/collector-script-20260914-r4/` in this
repository. The r3 directory is kept, and its job is unloaded.

- `publisher/`: clean publisher source at `628c3116`;
- `harvester/`: clean native source at `64b2263d`;
- `python/`: CPython 3.13.12 environment, synchronized from
  `harvester/server/uv.lock` with
  `uv sync --active --frozen --no-install-project`;
- `private/collection.json`: schema-2 plan with `patience_seconds` 600, SHA-256
  `d5f2f69c912553640f55e2e2ae03955ac16761a74f1dbde2dc2bbd123e88882a`;
- `private/publisher.toml`, `collection.env`, and `retry.json`: bound deployment;
- `private/it.gramscii.open-data-catalogue.collection.plist`: loaded job definition;
- `collection/state.json`, `stdout.log`, and `stderr.log`: progress and failures.

`publisher.toml` names `python/bin/python` and the r4 paths. `collection.env`
differs from r3's file only in `PLUGINS_DIR`, which names its own
`harvester/plugins` so that provider contracts come from the running revision.
The native `structure` command loads `CollectionSettings`: the database,
plugins directory, shared pacing and HTTP hosts. The file's remaining settings
still name the removed `/private/tmp/sdg-managed-composition-smoke-plan-20260911/`
tree; `structure` does not read them, and a plan with a `sync` step requires a
rebuilt environment.

The document contract of the deployed source is
`86743b8a6717b98f94853c90308e2653356199909c2d77dc2e2986063ea5f997`, measured
with `document-policy-status` at SDG `11795efc`; no file it pins changes between
that commit and `64b2263d`. At r3's `9f502ea6` it was
`9985f9d893fdb309a58825862927a8b59052617f1628eac6e2a6546025eb2cd9`: the contract
pins `providers.yaml`, which PR 164 changes.
`structure` does not read the contract; document regeneration requires a status
measured from the source it runs. The collection plan check passes, and the
native settings and ISTAT provider contract load with the deployment's
interpreter without provider requests. Quality thresholds remain unchanged.

The retry policy allows eight total attempts for a declared transient GET
failure, starting at 13 seconds with factor 2 and a 900-second backoff cap.
Provider Retry-After can extend that delay. A 429 without Retry-After defers the
shared gate for the explicitly configured 172800 seconds. These are operational
choices, not additional claimed official rate limits. Exhaustion stops with an
error; permanent failures do not enter a blind restart loop.

Inspect the active job and local state from this repository:

```sh
launchctl print gui/501/it.gramscii.open-data-catalogue.collection
cat build/collector-script-20260914-r4/collection/state.json
tail -n 30 build/collector-script-20260914-r4/collection/stderr.log
```

## Resuming after a restart or logout

The Mac must remain awake. The job is loaded in the current login session; it is
not installed for automatic loading at a later login. A restart ends the native
process without closing its run, and the partial unique index on running rows
then refuses every new run. The native command line never closes a running row.
Resume in this order:

1. Confirm that no `collect` or `sdg.plugins.opendata` process runs and that no
   client holds the collection database.
2. Close the interrupted run with the plugin's own function, from
   `build/collector-script-20260914-r4/harvester/server`. It closes every running
   row, so it runs only after step 1 finds no owner:

   ```sh
   env -i HOME="$HOME" LC_CTYPE=C.UTF-8 PATH=/opt/homebrew/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 \
     ../../python/bin/python -B -c 'from pathlib import Path
   from sdg import store
   from sdg.config import CollectionSettings
   from sdg.plugins.opendata import service
   settings = CollectionSettings(_env_file=Path("../../private/collection.env"))
   with store.connect(settings.database_url) as conn:
       print(service.close_interrupted(conn))'
   ```

3. Check the plan and the native environment. `--check` verifies digests, the
   harvester revision and a clean source; it does not start the interpreter, so
   also load the settings and the ISTAT provider with it:

   ```sh
   (cd build/collector-script-20260914-r4/publisher &&
     python3 -B ./collect --plan ../private/collection.json --check)
   (cd build/collector-script-20260914-r4/harvester/server &&
     env -i HOME="$HOME" LC_CTYPE=C.UTF-8 PATH=/opt/homebrew/bin:/usr/bin:/bin PYTHONNOUSERSITE=1 \
     ../../python/bin/python -B -c 'from pathlib import Path
   from sdg.config import CollectionSettings
   from sdg.plugins.opendata.__main__ import _providers
   settings = CollectionSettings(_env_file=Path("../../private/collection.env"))
   print(_providers(settings, "istat")[0].extra["dataflow_permanent_errors"])')
   ```

4. Load the same plist, then confirm a new run row, ISTAT admissions in the
   shared pacing store and newly written structures:

   ```sh
   launchctl bootstrap gui/501 "$PWD/build/collector-script-20260914-r4/private/it.gramscii.open-data-catalogue.collection.plist"
   ```

An already loaded, stopped job can be started with `launchctl kickstart
gui/501/it.gramscii.open-data-catalogue.collection` after its failure is examined.
Do not kill a live collection or remove its kernel lock to start another writer.
Missing inputs require an explicit rebuilt deployment under this repository's
`build/`, never in a temporary directory; another environment is never
substituted.

Completion and failure have configured local macOS notification commands.
Notification visibility depends on macOS preferences; no future chat message is
scheduled. The collector invokes no Codex or language model and consumes no
Codex tokens. This does not publish the dataset or its README: unresolved source
rights, metadata, document regeneration and strict release verification remain
separate work.
