# Local update deployment bootstrap, September 10, 2026

The real three-index update plan passes configuration, receipt, archive, consumer
pin and initial freshness checks. The launchd definition passes `plutil -lint`.
It is prepared but not installed or started: runtime pacing/resource adoption
and the final SDMX code integration must precede the first source acquisition.

## Persistent deployment

Publisher checkout:
`/Users/robertomarras/progetti/open-data-catalogue-updater`, detached at `919e78a`.
Harvester checkout:
`/Users/robertomarras/progetti/semantic-deterministic-graph-opendata-updater`,
detached at `6f0df27e`. The harvester must receive the verified final SDMX changes
while inactive before an ordinary update run.

All local configuration, copied archives, receipts, installed plugin resources
and runtime state live under the publisher's ignored `build/update-deployment/`:

- `publisher.toml`: real deployment and launchd settings.
- `plan.json`: explicit national, SSN and qualified Eurostat scopes; discovery
  action `retain`; full three-index README and viewer generation.
- `state.json`: schema 2, with real archive/publication/activation paths.
- `deployment.env`: mode `0600`, separate from every existing runtime environment.
- `bootstrap/`: four immutable local archives and their verification receipts.
- `plugins/opendata/`: installed mutable resources outside either source checkout.
- `runtime-plugin-maps.json`: per-runtime installed resources and Git blob proofs.
- `it.gramscii.open-data-catalogue.plist`: reviewed candidate, not installed.
- `deployment-qualification-installed-resources.json`: successful preflight and
  freshness evidence for the installed resource directory.

The configured cadence is 43,200 seconds, maximum run 32,400 seconds and reserve
3,600 seconds. The source operation budgets total 29,160 seconds; the run leaves
3,240 seconds for additional validation, upload and activation work. Every
updated scope declares a 24-hour lifetime, exceeding the complete 22-hour cadence
budget. These explicit limits are enforced; they do not guarantee source uptime.

The existing pins allow an immediate initial run, including its maximum duration
and reserve. Earliest expiry is SSN at
`2026-09-11T07:53:52.035944+00:00`; therefore the last possible bootstrap start
under these exact pins is `2026-09-10T21:53:52.035944+00:00`. Regenerate the
schedule immediately before installation to recheck that bound. No source
timestamps or lifetimes were extended.

## Discovery verification and index activation

`verify-catalogue` performed a new immutable HTTP readback of discovery revision
`8854722f8a035cbed57b1cb2bbbed4a297f5c188` from
`2026-09-10T13:34:53.086255+00:00` to
`2026-09-10T13:34:59.854229+00:00`.
The archive matched 55,034,326 bytes and SHA-256
`1e9eafeb4e691dc810d0de73fe387098b5029fcb740934d2fd4eb4ada56864e9`.
`bootstrap/catalogue-verification.json` records method `immutable-readback`,
the explicit artifact pin, start/completion times, `verified: true` and no error.
It does not claim a new upload or recreate a missing historical upload receipt.
The discovery quality defects remain unchanged.

SSN and Eurostat were reactivated at their existing verified pins in the isolated
updater deployment. Their new receipts retain the actual prior and resulting
pins. National activation retains its successful receipt from the
[national publication](2026-09-10-national-25-domains.md). The resulting state
exactly matches the updater's read-only `availability-status` output.

## Pacing and runtime resources

The environment uses the explicitly shared PostgreSQL pacing store,
`semantic_deterministic_graph_opendata_pacing`, egress `roberto-local-egress`,
5-second connection/statement budgets and 604,800-second admission retention.
All configured provider/channel policies passed the store's non-admitting probe.

The read-only census at `2026-09-10T13:39:23.655407+00:00` inspected 17 legacy gates
across the main, Bandi, publication and DVNS databases. None was future-dated.
The shared store contained three buckets and 431 admission receipts. Its existing
gates and receipts were preserved. No source request or admission claim was made
by the bootstrap. The census is a point-in-time record, not global rollout
certification; repeat it at cutover and preserve the maximum of any future gates.

Each runtime has its own installed plugin directory:

| Runtime | Resource source commit | Copied files | Other plugins |
| --- | --- | ---: | --- |
| Main | `d92fdeaad3bd48428c381dd3db331b69ff7b71e9` | 79 | dots-ocr, google, mistral-ocr, moduli, web-search |
| Bandi | `7f4f20ce8b87c55ecf20340024fd184c4e955d77` | 295 | bandi, dots-ocr, google, mistral-ocr, moduli, web-search |

The corresponding `PLUGINS_DIR` values are `runtimes/main/plugins` and
`runtimes/bandi/plugins` under the persistent deployment directory. Only their
`opendata` directories are symbolic links to the common installed
`plugins/opendata`. All other files were copied from their respective immutable
commits and all 374 copied blobs were checked against Git. Bandi's distinct
web-search revision remains preserved. No source checkout files or live
environment files were modified.

Both maps resolve `opendata/data/availability-selection.yaml` to the same mutable
policy used by the updater. The complete map manifest SHA-256 is
`016352950a35d63679ecf97ce47762fda9ffd0f7dd5ec7062bb3b154c64177d1`.
Resource mapping alone does not verify the final running server code; the runtime
owners must adopt the maps and shared pacing configuration at coordinated cutover.

## Local verification and pending activation

Publisher code `919e78a` passed all 98 local tests in 22.964 seconds on macOS,
including current readback provenance, failed readback receipts, local mismatch
before HTTP, schema-1 rejection and complete update state transitions. Ruff and
whitespace checks passed. The actual CLI verified discovery remotely, reactivated
the two auxiliary pins, validated the real state and generated a valid plist.
No native Linux/Windows execution is claimed. GitHub Actions remains disabled.

Before loading launchd, update the inactive harvester/resources with the verified
SDMX release, revalidate the state and resource manifests, complete both runtime
adoptions, and repeat the pacing/ownership census. Avoid overlapping acquisition
of an already active source scope. The generated service uses `RunAtLoad=true`,
so loading it starts source acquisition immediately. The first complete
authenticated scheduled run remains an outstanding qualification; no
`complete.json` is claimed for it.
