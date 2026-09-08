# Open Data catalogue publisher

Produces verified releases of the [catalogue on Hugging Face](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue).
The [SDG harvester](https://github.com/Gramscii-Git/semantic-deterministic-graph)
owns provider access, database tables and document indexing. This repository owns
release policy, archive validation, publication and publication receipts.
[Boundaries](https://github.com/Gramscii-Git/boundaries) is the separate geographic
asset repository; matching territorial codes and vintages must be checked.

The [published availability revision](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/de6a4bd676273ef2937119906e78cc94676b95ba/availability)
contains 72,341 joint combinations for five DVNS datasets across 23 completed
partitions. COFOG covers 34 geographies for 2014–2024; four OpenCivitas annual
datasets cover Calabria, Lazio and Lombardia. Source evidence has an explicit
24-hour selection lifetime; the archived evidence remains reproducible afterwards.
The seven-table discovery archive remains a separate, older release with recorded
quality defects. The [Hub card](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue)
describes both artifacts and their measured limits.

## Configuration

Python 3.11 or newer is required. The publisher itself uses only the standard
library. Copy `publisher.example.toml` to `publisher.local.toml`, then configure:

- The harvester checkout, its virtual-environment Python interpreter and the
  explicit `deployment.environment_file` path. The environment file may belong
  to a deployment separate from the source checkout. Interpreter paths retain
  their virtual-environment identity even when the executable is a symlink.
- The Hugging Face CLI command, logged in with write access to the target dataset.
  It must support `hf upload --json` returning a commit URL.
- The Hub endpoint, repository, branch, build directory and README template.
- Required providers, document languages, vocabulary requirements and release limits.
- The scheduler interpreter, executable search path, log path and calendar.

All fields are required and validated. Paths are resolved relative to the
configuration file. There are no implicit deployment paths or release thresholds.
The harvester must implement publication contract 1; an incompatible checkout is
refused before any catalogue mutation. Its embedder must be available for indexing.

## Commands

Every command requires an explicit configuration and action:

```sh
./update --config publisher.local.toml check --archive path/to/archive.tar.gz
./update --config publisher.local.toml prepare
./update --config publisher.local.toml refresh
./update --config publisher.local.toml publish
./update --config publisher.local.toml release
```

| Command | Provider/database work | Upload |
| --- | --- | --- |
| check | Reads only the named archive | No |
| prepare | Exports the database in a read-only, repeatable-read transaction | No |
| refresh | Syncs, invalidates changed structures, reads structures and vocabularies, rebuilds/indexes documents, verifies providers, then prepares | No |
| publish | Prepares and validates the current database | Yes |
| release | Refreshes, prepares and validates | Yes |

A partial structure harvest is an explicit failure, recorded by SDG, and prevents
subsequent publication. Provider timeouts are configured, not inferred. A failed
run is not retried automatically by this publisher.

Preparation writes to a unique directory under the configured build directory.
A local lock refuses overlapping publisher runs; SDG also owns its database job
guard. A lock left after a process crash requires inspection before removal.

## Release checks

Validation reads every JSONL row and checks the exact table set, row identities,
duplicates, manifest counts, catalogue references, provider coverage, vocabulary
references and configured completeness limits. No row is silently removed or
given an invented licence to make a release pass.

The example policy is deliberately strict: it rejects structure errors, missing
required structures/documents, missing licences, legacy vocabulary scopes and
missing structure-to-vocabulary mappings. Its minimum dataset count is an explicit
release baseline. Intentional coverage reductions require policy review.

A rejected preparation retains its archive and `quality.json` for inspection.
The published catalogue may predate this policy and fail it; that is not permission
to weaken the policy or present incomplete metadata as complete.

## Publication

### Joint availability artifacts

The shared availability index is separate from the seven-table discovery
snapshot. Its release contract records datasets and explicit indexing scopes,
completed source partitions and joint period/territory/dimension combinations.
It contains observation-presence states and source receipts, not measurement
values. Extraction timestamps must not be presented as observation periods.

The independent validation command is available:

```sh
./update --config publisher.local.toml check-availability \
  --archive build/availability.tar.gz --policy availability-policy.example.toml
```

Validation streams bounded records into a size-limited temporary SQLite
database. It rejects incomplete partition coverage, broken references,
duplicate combinations, mismatched dimensions and unbounded calendar periods.
Raw observations, unknown archive members and unsuccessful receipts are not
accepted. Dataset verification times retain the oldest source receipt; all
receipts must predate the snapshot, and evidence must still be valid at snapshot
time. Consumers must also enforce its expiry when selecting options.
### Constructing a declared availability scope

```sh
./update --config publisher.local.toml build-availability \
  --scope scopes/dvns-cofog.json --policy scopes/dvns-cofog.policy.toml
```

This runs SDG's native index adapter and validates its finished artifact. The
included scope covers DVNS `eurostat_cofog`, Italy, every year from 2014 through
2024. It does not declare coverage of other datasets or countries. The request
grid plans source reads; joint combinations come exclusively from returned
observations, including missing and suppressed cells. Zero remains observed.
No measurement values are stored in the published artifact format.

The harvester validates the live source integration and filter contract, shares
the deployment's provider quota and stages bounded source responses. Its DVNS
adapter accepts annual observations with complete unpaged or offset retrieval;
cursor, bounded-only and other period contracts are explicit refusals. Repeated
combinations, changed pagination totals, malformed observation paths, scope
mismatches, incomplete pages and exhausted resource budgets prevent completion.
Requests are not retried automatically.

Every build owns a unique directory. `source/progress.jsonl` records its declared
scope and partition states; a failed build retains `source/failure.json` and
produces no completed archive. A successful preparation contains
`availability.tar.gz`, `manifest.json`, `quality.json`, `scope.json` and
`SHA256SUMS`. The publisher independently verifies the exact datasets and every
request partition against the requested scope, in addition to archive contents.

Evidence expiry is measured from the oldest source receipt. The scope explicitly
declares per-response consistency: this is not an upstream dataset snapshot or a
source-version guarantee, and there is no automatic resume.
`build-availability` makes no upload and does not change a deployment's reader pin.

`scopes/dvns-expanded.json` declares the five-dataset scope described above;
use it with `scopes/dvns-expanded.policy.toml` for the wider build.

### Availability publication and Hub documentation

```sh
./update --config publisher.local.toml publish-availability \
  --directory build/availability-REPLACE_WITH_BUILD_ID --destination availability \
  --policy scopes/dvns-expanded.policy.toml --readme-template README.availability.md
```

Publication repeats independent archive and exact-scope validation, rejects
expired source evidence and uploads only the six declared public files under the
chosen repository directory. It preserves the separate discovery archive and its
root manifest. Every uploaded file is read back at the returned immutable commit
and verified against the local size and checksum.

The main Hub card is generated independently from the exact published artifacts:

```sh
./update --config publisher.local.toml publish-documentation \
  --catalogue-archive path/to/published-catalogue.tar.gz \
  --catalogue-revision FULL_CATALOGUE_COMMIT \
  --availability-archive path/to/availability.tar.gz \
  --availability-revision FULL_AVAILABILITY_COMMIT \
  --policy scopes/dvns-expanded.policy.toml --readme-template README.hub.md \
  --viewer-config viewer.json
```

Both archive downloads are verified at their supplied revisions before the new
card is uploaded. This command publishes only `README.md` and
`catalogue-quality.json`. It records whether the existing catalogue passes the
current strict policy; a failed catalogue policy remains visible and does not
authorize replacing that archive. Availability counts, periods, territory counts
and evidence expiries come from the validated index.

SDG's indexed-selection contract requires its own explicit pin, budgets, metadata
read allowlist and native argument bindings. Installing new reader code and
changing deployment pins are separate from publishing on the Hub; source or index
changes require renewed verification and confirmation.

### Discovery snapshot publication

Only a validated release directory is uploaded. One Hub commit carries the archive,
manifest, checksums, quality report and README rendered from `README.dataset.md`.
Counts and snapshot dates come from the archive, not hand-maintained prose.

The publisher uses the **commit returned by the upload**, never a later lookup of
`main`. It downloads every published file at that immutable revision and checks
its size and SHA-256. A mismatch fails explicitly; no second upload is attempted.

`publication.json` records the immutable URL, digest, size and verification result.
If remote verification fails after upload, the receipt retains the actual commit
with `verified: false`. Publication is not reported as verified in that state.
The receipt is local because its commit identity exists only after the upload.

Pin the verified immutable URL, SHA-256 and size in consuming deployments. Updating
a mutable branch must not break deployments pinned to an earlier release.

## Scheduling on macOS

Generate the launchd definition from the same validated configuration:

```sh
./update --config publisher.local.toml schedule --output build/catalogue.plist
plutil -lint build/catalogue.plist
```

This writes a plist; it does **not** install or start a job. The example schedules
`prepare`, without uploads. Selecting `release` explicitly enables publication
when that job is subsequently installed. Configure paths and credentials accessible
to the service, validate a release first, then install the generated definition
using launchd. Generation refuses to overwrite an existing output file.

The scheduler is not part of Linux or Windows installation. The CI matrix runs
the publisher's filesystem/HTTP contracts on macOS, Linux and Windows; a local
macOS test run alone does not verify the other operating systems.

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use isolated temporary archives, directories and local HTTP servers. They
perform no Hub writes. Actual authenticated publication is a separate release
qualification step and must not be inferred from local tests.

## Licence

Publisher code is MIT-licensed. Source metadata retains the original providers'
terms. Gramscii's compilation terms and source-rights boundaries are stated in
the dataset README template.

The documentation publication also generates the Hub viewer tables from the
verified archives. `viewer.json` declares each subset, split, source path and
column type. Only those JSONL files are selected by the dataset card; manifests
and quality reports are not loaded as data. Nested fields retain their JSON
content without provider-dependent column inference. `viewer-manifest.json`
records exact row counts, source archive hashes and output checksums.
