---
pretty_name: Open Data catalogue
license: other
license_name: per-dataset
license_link: https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/blob/main/README.md
language:
  - it
  - en
tags:
  - open-data
  - sdmx
  - statistics
  - availability
$viewer_metadata
---

# Open Data catalogue

This repository publishes independently versioned metadata and licensed source snapshots:

- A **discovery catalogue** with **$catalogue_datasets dataset entries** from
  ISTAT, Eurostat, OECD, ILO, DoveVannoINostriSoldi (DVNS) and Cruscotto Italia.
- **$availability_indexes independently pinned availability indexes** with
  **$availability_combinations joint combinations across $availability_datasets datasets**, built from complete
  source responses within the explicitly declared scope.
- **Licensed Cruscotto source snapshots**, stored separately from the metadata,
  preserve the source photographs used to construct the index.

The metadata archives contain no observation values. Availability indexes add evidence
about existing source datasets; its combinations are not additional datasets.
The archives include no search vectors or credentials.

## Browse the tables

The viewer exposes explicitly configured subsets, each with a `data` split:
`catalogue` contains all discovery entries. Each named availability index has
separate dataset and combination tables, retaining its own source revision.
These are metadata tables, not training examples or observation values.

Viewer tables are derived from the exact archives linked below. Nested metadata
is retained as JSON text so differing provider fields do not change the table
schema. Catalogue entries also retain their complete original row in `record_json`.
See [viewer integrity and source hashes](viewer-manifest.json).

## Verified availability

Each download identifies a full immutable publication commit. Counts and hashes
are verified against that index's archive independently.

| Index / pinned download | Built (UTC) | Datasets | Partitions | Combinations | Bytes | SHA-256 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
$availability_releases

| Index | Provider | Dataset | Source periods | Distinct territories | Combinations | Evidence expires (UTC) |
| --- | --- | --- | --- | ---: | ---: | --- |
$availability_rows

COFOG covers the geographies returned by DVNS for each indexed year, including
countries and European aggregates. Aggregates must not be added to their members.
The national OpenCivitas scope queries all 15 ordinary-statute regions. Its
separately named annual datasets retain their distinct municipality sets and
source contracts; they are not automatically comparable or additive. The table
reports actual source coverage for each dataset. These scopes do not cover every
dataset or year in the separate discovery catalogue.

The national Cruscotto scope indexes mapped domains with verified licences,
using the complete official municipality inventory. The exact codes and original
HTTP inventory receipt are published in [inventories.json](availability/inventories.json);
every domain's request grid is verified against that full list. A completed
municipality request does not imply that every domain contains measurements
there. Domain inclusion is recorded in the table and the published scope; a
licence alone does not certify availability. Air quality, weather and morphology retain their
physical units; weather periods identify forecast validity instants.
Annual observations retain calendar bounds. School years and other source
labels retain their native meaning without invented calendar bounds. Source
snapshot dates identify a published photograph, not historical observations.
Cruscotto accepts only a municipality argument and exposes no historical-period
query. Missing domains and measurements do not acquire a fabricated year.

The SSN index preserves the whole history returned by the native DVNS endpoint.
The Eurostat index covers only its explicitly qualified annual, monthly,
quarterly and daily series. It does not certify the entire Eurostat catalogue.
Non-geographic series retain an explicit null territory, displayed as zero
distinct territories; weekends and other source gaps are not fabricated.

The index preserves actual period/territory/dimension combinations and source
receipts. `observed`, `missing` and `suppressed` are distinct; observed zero is
not missing. Numeric values are acquired after selection and confirmation, using
the original source or an explicitly pinned licensed source snapshot. Consumers
must reject expired evidence and changed
source definitions. The expiry limits use for new selections; it does not delete
this reproducible historical artifact.

See [the index contract](availability/README.md),
[declared scope](availability/scope.json), [inventory evidence](availability/inventories.json) and
[independent validation](availability/quality.json).

The [source snapshot manifest](source-snapshots/manifest.json) binds the exact
availability digest and dataset definitions to immutable response shards. It
records original HTTP receipts, permitted projection fields, licences,
attribution and source URLs. Cruscotto's native photographs can be regenerated
during a national scan; archived acquisition retains the confirmed source time
and values. It must fail on missing or altered archive bytes without replacing
them with a newer native response. Undeclared and unlicensed domains are excluded.
Readers pin the manifest and response files to their full publication revision.

## Discovery catalogue

Snapshot: **$catalogue_taken_at**. The discovery archive is a separate release;
publishing the availability index does not refresh its seven tables or certify
that every catalogue entry is ready for acquisition.

| Provider | Catalogue entries |
| --- | ---: |
$catalogue_providers

| Table | Rows |
| --- | ---: |
$catalogue_tables

The archive contains one JSONL file per table and `manifest.json`. Each line is
a stored row, preserving provider identifiers, source metadata and timestamps.
Descriptions, structures, vocabulary labels and licences can be missing. Inclusion
in the catalogue alone does not prove observation availability or permission to
reuse a dataset.

[Download the pinned discovery archive]($catalogue_url).
Size: **$catalogue_bytes bytes**. SHA-256: `$catalogue_sha256`.

### Measured catalogue limitations

The currently published discovery archive **$catalogue_status** the publisher's
current strict release policy. The checks below were run against the exact
published bytes; see [the policy and report](catalogue-quality.json).

| Check | Recorded count |
| --- | ---: |
$catalogue_metrics

Structure errors, missing metadata and unresolved vocabulary references remain
release defects. They are not made acceptable by publishing the availability
index. A corrected catalogue release must pass the required checks before it
replaces the current archive. Counts above describe this published archive,
not an unpublished working database.

## Integrity and updates

Use the full commit hashes in the download links above. Branch names such as
`main` can move and must not be treated as permanent addresses for a fixed hash.
The catalogue's root `manifest.json` and `SHA256SUMS` describe the discovery
archive. The availability directory has its own manifest and checksums.

The [publisher](https://github.com/Gramscii-Git/open-data-catalogue) owns explicit
coverage, independent validation and publication receipts. The
[SDG harvester and reader](https://github.com/Gramscii-Git/semantic-deterministic-graph)
own provider access and plugin integration. An HF update does not automatically
upgrade deployed plugin code or replace an installation's immutable pin.

Geographic boundaries live in
[Gramscii-Git/boundaries](https://github.com/Gramscii-Git/boundaries).
Map joins require matching code systems and territorial vintages. Universal
coverage of every historical catalogue code is not guaranteed.

## Rights and provenance

Consult each dataset's source terms. Metadata fields retain recorded licences,
attribution and source links where available; a missing licence is not replaced
with an assumed one. This compilation does not expand upstream reuse rights.

Gramscii's own assembly and documentation are offered under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), applying to Gramscii's
contribution rather than granting additional rights to the underlying sources.
