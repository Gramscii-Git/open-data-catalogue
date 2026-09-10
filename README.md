# Open Data catalogue publisher

Produces verified releases of the [catalogue on Hugging Face](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue).
The [SDG harvester](https://github.com/Gramscii-Git/semantic-deterministic-graph)
owns provider access, database tables and document indexing. This repository owns
release policy, archive validation, publication and publication receipts.
[Boundaries](https://github.com/Gramscii-Git/boundaries) is the separate geographic
asset repository; matching territorial codes and vintages must be checked.

The [published availability revision](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/a6c77126656f5b4fc3ae782268f14822c0039919/availability)
contains 888,000 joint combinations for five DVNS datasets and 24 Cruscotto domains
across 189,575 completed partitions. COFOG covers 34 geographies for 2014–2024;
four OpenCivitas annual datasets cover all 15 ordinary-statute regions. Cruscotto
covers the complete 7,896-municipality inventory. Its
[licensed source snapshots](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/e55e80da98d9e801f54d25efcc5d911f630c78a6/source-snapshots)
preserve the original responses in 256 immutable shards, with source receipts,
licences and attribution. Source evidence has an explicit
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

`scopes/ssn-history.json` declares the complete source-provided national SSN
history. `scopes/eurostat-qualified-series.json` declares four qualified native
series: annual agriculture, monthly consumer prices, quarterly GDP and daily
exchange rates. Their exact countries, dimensions and periods live in the
scope files; they do not represent the full Eurostat catalogue. Each has a
separate validation policy and can be published and activated independently of
the national municipality index. The September 10 builds validate 65 SSN and
60 Eurostat combinations; their per-index README files record evidence expiry.

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
`availability.tar.gz`, `manifest.json`, `quality.json`, `scope.json`, `inventories.json` and
`SHA256SUMS`. The publisher independently verifies the exact datasets and every
request partition against the requested scope, in addition to archive contents.

Evidence expiry is measured from the oldest source receipt. The scope explicitly
declares per-response consistency: this is not an upstream dataset snapshot or a
source-version guarantee, and there is no automatic resume.
`build-availability` makes no upload and does not change a deployment's reader pin.

An operator can explicitly reconstruct an index from retained native responses
after correcting its projection. Seal the response directory with the harvester's
`seal-availability-capture --responses <directory> --to <manifest>` command and
retain the returned manifest digest. Pass the resolved version-1 scope and its
original inventory evidence to the publisher:

```sh
./update --config publisher.local.toml build-availability \
  --scope build/resolved-scope.json --policy scopes/verified-selection.policy.toml \
  --capture build/source/responses --capture-manifest build/capture.json \
  --capture-sha256 <manifest-sha256> \
  --inventory-evidence build/inventories.json --inventory-sha256 <inventory-sha256>
```

All capture arguments are required together. This path reads neither source
observations nor the municipality inventory from the network. It verifies the
pinned capture and inventory, retains original receipts and evidence expiry,
and refuses missing requests or changed bytes. It writes a new complete archive;
it does not continue a partially written index or renew source freshness.

Mutable source photographs require an explicit archived source mode. Add
`--snapshot-provider cruscotto --snapshot-shard-prefix-length 2` to the build
command to stage licensed response projections in `source/snapshots` alongside
the metadata archive. Both snapshot arguments are required together. Prefix
length controls the source-digest grouping; a shard exceeding the declared
response budget fails the build. Source timestamps and HTTP receipts remain
unchanged. The manifest records licence, attribution, source URL and permitted
fields for each archived dataset; undeclared domains are excluded.

Publish the source snapshots independently, linked to the completed index:

```sh
./update --config publisher.local.toml publish-snapshots \
  --directory build/availability-BUILD_ID/source/snapshots \
  --availability build/availability-BUILD_ID/availability.tar.gz \
  --destination source-snapshots --policy scopes/verified-selection.policy.toml
```

The publisher verifies the index, every source receipt, complete provider scope,
projection rights, file inventory and content digest before upload, then reads
back every published file at its immutable revision. These snapshots contain
licensed source values; the availability archive contains only selection metadata.

`scopes/dvns-expanded.json` declares the five-dataset scope described above;
use it with `scopes/dvns-expanded.policy.toml` for the wider build.

`scopes/verified-selection.json` declares all 15 ordinary-statute regions for
the four OpenCivitas datasets, all native COFOG geographies for 2014–2024, and
the mapped, licensed Cruscotto domains for the complete official municipality
inventory. Use `scopes/verified-selection.policy.toml` for its build and
publication. The source integration supports 25 domains, including ANNCSU under
its verified CC BY 4.0 terms; the published national revision linked above still
contains 24 domains. A new complete build and publication are required before
ANNCSU can be counted as indexed coverage. Air quality, weather and morphology
retain their physical units.
Calendar periods, weather validity instants, source snapshot dates and opaque
source labels remain distinct. An unreported domain never receives invented
observations or a guessed period.

Publisher scope schema 2 requires an explicit `inventories` object. A request
grid may list values directly or name an inventory using
`{"inventory": "municipalities"}`. Every inventory declares a direct HTTPS URL,
code field and pattern, byte and row limits, and timeout. The publisher reads
each inventory once, validates every code, and expands every reference to the
complete sorted code list. Invalid or duplicate codes, redirects and budget
violations fail the build; no municipality is silently omitted. Explicit scopes
without inventories declare `"inventories": {}`.

The native harvester receives a fully resolved schema-1 `scope.json`.
`inventories.json` preserves the complete source code lists, original inventory
specifications, HTTP receipts and their dataset/argument bindings. Publication
verifies that each bound request grid equals its recorded inventory exactly.

Within one build, identical native requests share their original response body
and receipt, stored under `source/responses/`. Thus the 24 Cruscotto domains use
one native municipality response each, rather than 24 separate source reads.
Checksums are verified on reuse. Every new build acquires its own responses;
corrupt or unavailable evidence fails explicitly and is never replaced by a
hidden refetch. Provider quota and total-response budgets still apply. The
national scan can take several hours; its operation deadline and all memory,
disk and validation budgets are explicit scope policy.

### Availability publication and Hub documentation

```sh
./update --config publisher.local.toml publish-availability \
  --directory build/availability-REPLACE_WITH_BUILD_ID --destination availability \
  --policy scopes/verified-selection.policy.toml --readme-template README.availability.md
```

Publication repeats independent archive and exact-scope validation, rejects
expired source evidence and uploads only the seven declared public files under the
chosen repository directory. It preserves the separate discovery archive and its
root manifest. Every uploaded file is read back at the returned immutable commit
and verified against the local size and checksum.

The main Hub card is generated independently from the exact published artifacts:

```sh
./update --config publisher.local.toml publish-documentation \
  --catalogue-archive path/to/published-catalogue.tar.gz \
  --catalogue-revision FULL_CATALOGUE_COMMIT \
  --availability-releases documentation-releases.local.json \
  --readme-template README.hub.md \
  --viewer-config viewer.json
```

Copy `documentation-releases.example.json` and supply the local archive, full
publication commit, repository destination and validation policy for every index.
Local file paths are resolved relative to that configuration. The viewer must
explicitly cover exactly the same set of archives.

Every archive download is verified at its supplied revision before the new
card is uploaded. This command publishes `README.md`, `catalogue-quality.json`,
the configured viewer tables and their integrity manifest. It records whether the existing catalogue passes the
current strict policy; a failed catalogue policy remains visible and does not
authorize replacing that archive. Availability counts, periods, territory counts
and evidence expiries come from the validated index.

SDG's indexed-selection contract requires its own explicit pin, budgets, metadata
read allowlist and native argument bindings. After publication, activate the
verified receipt in the SDG deployment selected by `deployment.harvester` and
`deployment.environment_file`:

```sh
./update --config publisher.local.toml activate-availability \
  --index national \
  --publication build/publication-REPLACE_WITH_BUILD_ID/publication.json \
  --expect-sha256 CURRENT_CONSUMER_ARCHIVE_SHA256
```

The consumer downloads the immutable archive, verifies its bytes, imports it
under the configured storage limits and checks that every dataset bound to
`--index` is present, unexpired and has the required axes. The schema-2 consumer
configuration names each dataset's index explicitly and keeps snapshot pins
inside that index. Other indexes and their bindings remain unchanged. Only then
does activation atomically update
the deployment's `availability-selection.yaml` and make the imported index
available. The receipt must identify the same configured repository and artifact
path. An unverified publication, a stale expected digest or a concurrent
configuration edit fails explicitly. Failed verification preserves the active
pin. The publisher records a successful result in `build/activation-*/activation.json`.

For archived providers, also pass `--snapshot-publications path/to/snapshots.json`.
That JSON object maps provider identifiers to the corresponding verified
publication receipt paths. Activation verifies the snapshot manifests against
the new index and all expected source responses before changing either pin.
An active archived provider requires explicit snapshot publication receipts on
the next activation. The plugin downloads observation shards only after the user
confirms a selection, retaining the original source time when upstream data changes.

Publishing and activation are explicit operator steps. Repeat the build,
publication and activation before the source evidence expires; publishing to
the Hub alone does not refresh a deployment. Source or index changes require
renewed selection verification and confirmation. Installing new reader code is
separate from activating a new data revision.

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

The scheduler is not part of Linux or Windows installation. Platform
qualification requires running the publisher's filesystem/HTTP contracts on
each native operating system. A local macOS test run alone does not verify
Linux or Windows.

## Verification

Verification runs locally; GitHub hosts code, history and pull requests.
GitHub Actions is disabled for this repository. Before merging code changes,
run the complete suite in an isolated checkout, lint the affected Python
modules and tests, and perform the relevant CLI and publication checks.
Record the tested commit, commands, platform, results and any checks not run
in the pull request. Integration changes must also be verified before merging.

```sh
python3 -m unittest discover -s tests -v
```

Tests use isolated temporary archives, directories and local HTTP servers. They
perform no Hub writes. Actual authenticated publication is a separate release
qualification step and must not be inferred from local tests.
Documentation-only changes require diff and reference review without rerunning
unaffected runtime tests. Unavailable native platforms remain explicitly
unverified. Missing remote checks do not waive the required local checks.

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
