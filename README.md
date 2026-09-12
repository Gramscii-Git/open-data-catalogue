# Open Data catalogue publisher

Produces verified releases of the [catalogue on Hugging Face](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue).
The [SDG harvester](https://github.com/Gramscii-Git/semantic-deterministic-graph)
owns provider access, database tables and document indexing. This repository owns
release policy, archive validation, publication and publication receipts.
[Boundaries](https://github.com/Gramscii-Git/boundaries) is the separate geographic
asset repository; matching territorial codes and vintages must be checked.

The [Hub card corrected on September 12, 2026](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/f3930bb41012ae41d68902f171389ec09afec290)
retains a September 7 discovery snapshot and three historical availability
indexes. All 35 indexed datasets' selection evidence expired on September 11;
none is current evidence for a new selection. The discovery archive remains
schema 1 with recorded quality defects and no admission under the current
schema-2 contract. These artifacts remain reproducible; updating their card
does not refresh their source evidence or qualify a new dataset release. The
[publication review](docs/audits/2026-09-12-hub-release-state.md) records the exact
archive pins and the publisher, updater and boundary responsibilities.

The [historical national availability revision](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/fc82d7bd8154da355a45a81d772615306413fdc9/availability)
contains 911,670 joint combinations for five DVNS datasets and 25 Cruscotto domains
across 197,471 completed partitions. COFOG covers 34 geographies for 2014–2024;
four OpenCivitas annual datasets cover all 15 ordinary-statute regions. Cruscotto
covers the complete 7,896-code universe returned by its source inventory on
September 10, 2026. The [inventory receipt](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/raw/fc82d7bd8154da355a45a81d772615306413fdc9/availability/inventories.json)
records retrieval at 07:56:02 UTC and HTTP Last-Modified September 5, 2026.
These source dates do not establish an administrative vintage or the current
number of Italian municipalities. Its
[licensed source snapshots](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/tree/eaeeae1eca695583e2e4c1ae6fa956fd13c05023/source-snapshots)
preserve the original responses in 256 immutable shards, with source receipts,
licences and attribution. Source evidence has an explicit
24-hour selection lifetime, expiring September 11 at 07:56–08:11 UTC for this
release; the archived evidence remains reproducible afterwards. ANNCSU adds
23,670 combinations across 7,890 source municipality codes; six completed
municipality responses contain no ANNCSU observations. See the
[release audit](docs/audits/2026-09-10-national-25-domains.md) for exact pins and limits.
The seven-table discovery archive remains a separate, older release with recorded
quality defects. The [Hub card](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue)
describes both artifacts and their measured limits.

## Configuration

Python 3.11 or newer is required. The publisher itself uses only the standard
library. Copy `publisher.example.toml` to `publisher.local.toml`, then configure:

- The harvester checkout, its virtual-environment Python interpreter and the
  explicit `deployment.environment_file` path and `deployment.process_environment`
  string mapping. The environment file may belong
  to a deployment separate from the source checkout. Interpreter paths retain
  their virtual-environment identity even when the executable is a symlink.
- The Hugging Face CLI command, logged in with write access to the target dataset.
  It must support `hf upload --json` returning a commit URL.
- The Hub endpoint, repository, branch, build directory and README template.
- Required providers, document languages, vocabulary requirements and release limits.
- The scheduler interpreter, executable search path, log path and calendar.

Publisher configuration schema 3 requires the complete process environment for
harvester and offline-projection children. They inherit no shell variables.
Declare operating-system, certificate, proxy, temporary-directory and cache
settings there when the deployment requires them. An explicitly empty mapping
passes none of those values. `PYTHONPATH` is reserved for the declared source
roots and cannot be supplied in the mapping.

The native SDG CLI receives `--env-file` unchanged. SDG gives an explicitly
declared process variable precedence over the same setting in that file; use
one location for each setting unless an intentional override is required. Such
an override must appear in `process_environment`, never just in the invoking
shell. Values are literal strings: no shell expansion or environment merge is
performed. Secrets belong in the private local configuration, outside Git.
This child boundary also applies when the publisher is launched by its schedule;
the separate authenticated Hugging Face CLI retains its own environment.

The selected core validates `OPENDATA_PACING`. Its current contract requires
`database_url`, `egress_id`, `dispatch`, `connect_timeout_seconds`,
`statement_timeout_seconds`, `receipt_retention_seconds` and `tcp_keepalive`;
the latter declares `idle_seconds`, `interval_seconds` and `probe_count`.
An absent or invalid field is an error. These values must describe the same
coordinated egress store as every participating caller. Loading publisher
configuration does not admit provider traffic or attest that coordination.
Archived configurations remain historical evidence and are not upgraded
automatically.

Discovery snapshots use schema 2 and carry the validated document-language
contract and projection provenance. `quality.document_contract_sha256` pins that
exact contract; obtain it from the configured harvester's `document-policy-status`
command and review its provider languages, authorities and query routes before
changing the deployment configuration. The example pin matches OpenData core
commit `b1c4fd11`; the final installed code requires its own verified pin.
The contract includes an explicit renderer manifest and hashes of its executed
modules, provider configuration, external words and input schema. Each document
binds its actual catalogue fields, structure, metadata report, localization
vocabulary, content and declared language authority to that contract. A change
to one of those inputs requires rebuilding its affected projections.

Native metadata documents retain their source language. Eurostat, OECD and ILO
require English documents; Italian discovery searches the explicitly declared
English and Italian stores together. DVNS English workspace definitions declare
`workspace_definition` authority. Italian section labels do not make native
English prose an Italian source document.

Publication requires zero missing required documents, zero documents outside the
declared current membership, and valid provenance and content hashes. Catalogue
records and source receipts remain preserved when obsolete derived documents
are reconciled. Old schema-1 discovery artifacts remain historical evidence and
are explicitly refused as current schema-2 releases; they must be reconstructed
from retained metadata with the current contract. Availability indexes and their
source snapshots have independent schemas and are unaffected by this discovery
contract change.

All fields are required and validated. Paths are resolved relative to the
configuration file. There are no implicit deployment paths or release thresholds.
The harvester must implement publication contract 2; an incompatible checkout is
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
A kernel-held lock refuses overlapping publisher runs; SDG also owns its database
job guard. The persistent lock file is not proof of a live owner and must not be
unlinked. Inspect the recorded owner and phase receipts after an interrupted run.

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

Four additional DVNS scopes are authoring inputs, with no publication or active
reader pin supplied:

| Scope | Declared coverage | Retained native qualification |
| --- | --- | --- |
| `dvns-cursor-observations` | Complete SIOPE entity census and hospital-bed corpus | Both complete traversals |
| `dvns-irpef-history` | Declaration years 2017–2025, all source table families | Annual metadata; complete 2021 bonus tables |
| `dvns-municipal-receipts-history` | Native national municipal receipts, source years 2024–2026 | Complete Calabria 2025 traversal and exact country/region/entity acquisitions |
| `dvns-siope-payments` | Complete ASL, province, region and metropolitan-city payment corpora | First page of each; complete acquisition still required |

Each JSON scope has a matching `.policy.toml` file. The component configuration
`scopes/dvns-observations.selections.json` declares four verified acquisition
bindings for future deployment assembly; it is not an activatable reader policy.
The four large payment datasets require native qualification of an entity filter
before adding their selection bindings. Coverage, temporal axes, resource limits
and the remaining publication gates are recorded in the
[DVNS selection audit](docs/audits/2026-09-10-dvns-selection-scopes.md).

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
adapter accepts observations through explicitly declared complete unpaged,
offset or cursor retrieval contracts. Unsupported bounded-only retrieval and
period contracts are explicit refusals. Repeated
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
retain the returned manifest digest. Pass the resolved version-2 scope and its
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

### Explicit offline SDMX graph provenance

Separately retained native graph responses may lack the original request digest
and full header map required by HTTP capture. They cannot be inserted into a
capture by inventing that metadata. A producer-only offline path accepts their
original short receipts and bodies as distinct pinned inputs:

```sh
./update --config publisher.local.toml check-offline-availability \
  --provenance build/offline/provenance.json \
  --provenance-sha256 <input-manifest-sha256> \
  --policy scopes/eurostat-qualified-series.policy.toml
```

The strict version-2 manifest has kind `sdmx-native-graph-reprojection`. It
declares `original`, `candidate`, `scope` and `inventories` assets; each asset
contains a canonical relative `path`, exact `bytes` and `sha256`. All paths
remain under the manifest directory. `configuration` pins `providers.yaml`,
`sdmx-query.yaml` and `levels.yaml` in one directory. `capture` declares a pinned
original capture `manifest` and its relative `responses` directory. Each entry
in `graphs` identifies `provider`, `dataset_id`, and pinned `receipt` and `body`
assets. Each entry in `definitions` declares those dataset identities and the
exact `original` and `candidate` definition digests. `core` declares its full
commit `revision` and a `files` mapping of every `server/sdg/**/*.py` file,
relative to `server/sdg`, to its digest. Verification has no elapsed-work
deadline. These are required inputs; the command infers no missing version,
scope, timestamp or digest.

The configured harvester Python executes the existing SDG parsers in a worker
that rejects every network and database connection. The worker checks the core
filesystem against both the declared manifest and actual commit blobs, then
checks every imported SDG module's origin and digest. It reconstructs every
definition from the exact dataflow/DSD graph, complete referenced domains and
original Actual constraint; it reconstructs every combination from the original
captured observations. Partition and combination table bytes must be unchanged.
Dataset changes are limited to the declared definition digests. Source clocks
and expiry cannot change; assembly time must be real and evidence still valid.
The configured availability policy bounds manifest, individual and aggregate
input bytes, archive records and temporary SQLite storage.

After review, the explicit publication command repeats the whole verification
before any remote effect:

```sh
./update --config publisher.local.toml publish-offline-availability \
  --provenance build/offline/provenance.json \
  --provenance-sha256 <input-manifest-sha256> \
  --policy scopes/eurostat-qualified-series.policy.toml \
  --destination availability/eurostat-series \
  --readme-template README.availability.md
```

It publishes the seven ordinary availability files plus
`offline-provenance.json`, binding the archive, input manifest, original asset
hashes, graph URLs/clocks, core commit/files and observed Python/library versions.
The lockfile digest identifies project evidence; it does not certify an
identical runtime on another machine. The ordinary publication command refuses
an offline provenance marker without its explicit verified path. No consumer
archive schema changes, automatic retries or source fallbacks are introduced.

Keep the input manifest, original archives, graphs, receipts and captured bodies
in their durable local bundle. The public report contains hashes and short
receipts, not the XML/CSV bodies, complete HTTP headers or measurement values.
It neither publishes those source bodies nor grants additional source rights.
The publication and consumer activation remain separate actions.

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
the mapped, licensed Cruscotto domains for the complete source municipality
inventory. Use `scopes/verified-selection.policy.toml` for its build and
publication. The published national revision linked above indexes 25 domains,
including ANNCSU under its verified CC BY 4.0 terms. Air quality, weather and morphology
retain their physical units.
Calendar periods, weather validity instants, source snapshot dates and opaque
source labels remain distinct. An unreported domain never receives invented
observations or a guessed period.

Publisher scope schema 3 requires an explicit `inventories` object. A request
grid may list values directly or name an inventory using
`{"inventory": "municipalities"}`. Every inventory declares a direct HTTPS URL,
code field and pattern, byte and row limits, and timeout. The publisher reads
each inventory once, validates every code, and expands every reference to the
complete sorted code list. Invalid or duplicate codes, redirects and budget
violations fail the build; no municipality is silently omitted. Explicit scopes
without inventories declare `"inventories": {}`.

The native harvester receives a fully resolved schema-2 `scope.json`.
`inventories.json` preserves the complete source code lists, original inventory
specifications, HTTP receipts and their dataset/argument bindings. Publication
verifies that each bound request grid equals its recorded inventory exactly.

Within one build, identical native requests share their original response body
and receipt, stored under `source/responses/`. Thus the 25 Cruscotto domains use
one native municipality response each, rather than 25 separate source reads.
Checksums are verified on reuse. Every new build acquires its own responses;
corrupt or unavailable evidence fails explicitly and is never replaced by a
hidden refetch. Provider quota and total-response budgets still apply. The
national scan can take several hours. Its memory, disk, request, byte and
validation budgets are explicit scope policy; valid work has no total deadline.

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

An existing discovery publication can have a schema that the current export
contract refuses. Document its original measured report explicitly instead of
treating it as a new export or silently changing inspectors:

```sh
./update --config publisher.local.toml publish-reported-documentation \
  --catalogue-evidence catalogue-evidence.local.json \
  --catalogue-status-artifact catalogue-status.json \
  --availability-releases documentation-releases.local.json \
  --readme-template README.hub.reported.md --viewer-config viewer.json
```

The evidence JSON has exactly `schema_version: 1`, `archive` and `quality_report`.
Each pin requires `path`, `revision`, `url`, `sha256` and positive integer `bytes`.
Paths are relative to the evidence file; URLs must identify the configured HF
repository's discovery archive and `catalogue-quality.json` at their full commit
hashes. The report must identify the exact archive, manifest and historical
policy. Both files are read back at their immutable revisions before staging.
Unknown fields, mutable revisions, changed bytes and inconsistent identities
fail explicitly.

This command preserves the original `catalogue-quality.json` bytes and adds the
explicitly named status artifact. The status records the two immutable pins,
current policy and its digest, required/observed snapshot schema,
`current_quality_evaluation: not_performed` and `admitted: false`. Matching the
current schema alone is not admission. The separate template attributes the
measurements to the original report and links the current status. The ordinary
`publish-documentation` and every new export remain subject to the strict current
inspector; an inspector failure never switches modes.

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

Publishing and activation are explicit operator steps, or named stages of the
validated update plan described below. Repeat the build,
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

### Complete local update plans

`run-update` completes the declared availability builds, source snapshot uploads,
immutable readback, consumer activation and Hub card/viewer publication in one
explicit run. Each index has its own scope, policy, destination and snapshot
settings. The plan may update a subset of the deployment's indexes while the
card retains the complete explicitly pinned set. No index is inferred from a
provider name or the current Hub branch.

Copy `update-plan.example.json` and `update-state.example.json` to local files.
The state must name real existing archives, verified publication receipts and
successful activation receipts for every deployed index. State schema 2 requires
`catalogue.verification` to identify a successful current readback of the existing
discovery archive. This proof is separate from the historical upload receipt and
does not claim that a publication occurred during verification. Configuration
paths are relative to their owning file. State schema 1 is rejected; there is no
automatic migration or reconstruction from `main`.

Update plan schema 3 requires `documentation.catalogue` with an explicit `mode`.
`current_validation` accepts exactly that field and uses the current inspector.
`published_report` also requires `evidence` and `status_artifact`, and is valid
only with discovery action `retain`. Its archive pin must equal the retained
state's verified archive. The run verifies both evidence publications before
collecting any source data and repeats verification when preparing the card.
Earlier plan schemas or missing mode are rejected; operational plans must be
reviewed explicitly rather than inferred or upgraded automatically.

Create the discovery proof from an explicitly pinned immutable revision, local
archive, expected checksum and byte count:

```sh
./update --config publisher.local.toml verify-catalogue \
  --archive path/to/open-data-catalogue.tar.gz --revision FULL_IMMUTABLE_COMMIT \
  --expect-sha256 EXPECTED_ARCHIVE_SHA256 --expect-bytes EXPECTED_ARCHIVE_BYTES \
  --output build/catalogue-verification.json
```

The command verifies local bytes before making a Hub request, then checks the
remote size and checksum. It writes a distinct `immutable-readback` receipt with
start/completion timestamps and explicit success or failure. Existing output is
never overwritten. No upload, metadata quality waiver, source request or reader
activation occurs. Discovery `publish` and `release` stages preserve their upload
receipt and also create this independent readback proof for the updated state.

```sh
./update --config publisher.local.toml check-update --plan update-plan.local.json
./update --config publisher.local.toml run-update --plan update-plan.local.json
```

`check-update` validates paths, receipt identities, archive hashes, viewer scope,
source policies, configured lifetimes and the read-only consumer
`availability-status` contract. It performs no source reads, uploads or consumer
mutation. `run-update` repeats the active-pin comparison before collection and
after activation. A stale state file fails before new source collection.

Discovery behavior is required independently: `retain` documents the supplied
published archive and its measured quality defects; `publish` validates and
publishes the current database; `release` first syncs, harvests, enriches and
verifies it. Strict discovery gates remain unchanged. `retain` does not claim
that the discovery catalogue has been refreshed.

The plan's cadence declares `interval_seconds`, `expected_run_seconds` and
`minimum_remaining_seconds`. The expected duration is a planning estimate,
shorter than the interval, and never cancels running work. Every updated
dataset's evidence lifetime must cover the interval, expected duration and
reserve together. The archive must still cover that future boundary and the
reserve measured from the actual current time before publication and activation.
The oldest original source evidence determines validity. Reconstruction and
publication never renew source timestamps or lifetimes.

The example declares a 12-hour interval, a 9-hour execution estimate and a 1-hour
reserve against 24-hour evidence. Qualify these estimates against measured
deployment throughput. Exceeding an estimate does not terminate an acquisition,
parser, database transaction, upload or readback. Expired evidence still fails
admission. Sleeping computers, source outages and missed jobs can leave expired
evidence; the consumer must keep refusing it.

Publisher configuration schema 3 requires `deployment.stop_grace_seconds` for
command shutdown after cancellation, owner death or an unclosed child process.
Each harvester, upload and offline-verification command has a supervisor with an
owner-lifetime pipe and a separate process group. Owner shutdown closes the pipe;
the supervisor terminates the group and reaps its command before exiting. A
command that exits with background processes still running is an explicit
failure. The shutdown grace controls TERM-to-KILL escalation only; it is never
an operation limit. The examples declare `hub.timeout_seconds = "unbounded"`
and inventory `timeout_seconds: null`. A finite socket inactivity limit requires
an explicit, justified transport requirement and never bounds total transfer
duration. Obsolete configuration fields and operational scope versions are
rejected explicitly.

Each execution owns `build/update-*/`. `progress.jsonl` is flushed to disk before
and after every phase, including its output directory and errors. Original
publication receipts survive failed remote readback. Successful activations
advance the state file atomically, immediately after each confirmed index;
`complete.json` exists only after the card and viewer are verified as well.
`failure.json` records interrupted or failed runs. The build lock and state lock
refuse concurrent mutation, including plans using different build directories
but the same state file.

Build and state locks use kernel-held file locks. Each command supervisor
inherits the active descriptors, so owner death does not admit a second writer
while the old command is stopping. The lock is released only when the execution
and all its command supervisors close their descriptors. Persistent lock files
are not evidence of a running owner and are never unlinked during normal use;
unlinking would permit concurrent locks on different inodes. An obsolete lock
directory is rejected and requires explicit operator reconciliation.

A later failure does not undo a verified upload or a successful activation of an
earlier independent index. There is no automatic retry or resume. Inspect the
phase receipts and actual consumer status before starting a new run. A crash
between consumer activation and saving its state requires explicit receipt
reconciliation; the next preflight refuses the mismatched pin. A process killed
without cleanup can leave a last `started` phase: inspect its owner and supervised
commands before starting another run. Keep the persistent lock file and these
runtime records outside version control.

To schedule this explicit pipeline, replace the calendar fields in `[schedule]`
with its plan and matching interval:

```toml
[schedule]
label = "it.gramscii.open-data-catalogue"
python = "../semantic-deterministic-graph/server/.venv/bin/python"
path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
log = "build/schedule.log"
action = "run-update"
plan = "update-plan.local.json"
interval_seconds = 43200
run_at_load = true
```

`run_at_load` is required for `run-update`. A true value starts the first run
when launchd loads the job; a false value waits for the declared interval.
Schedule generation checks the verified initial archives against that wait,
the expected run duration and the reserve, measured from generation time.
An index that is already five hours old cannot cover a twelve-hour wait plus
a nine-hour run and a one-hour reserve with a twenty-four-hour lifetime.
It can cover an immediate first run with the same duration and reserve.
Generate the definition immediately before loading it; regenerate and recheck
if installation is delayed. This check cannot guarantee execution on a sleeping
or unavailable computer. The timer behavior is defined by Apple's
[launchd configuration contract](https://github.com/apple-oss-distributions/launchd/blob/main/man/launchd.plist.5).

### Launchd definition

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
