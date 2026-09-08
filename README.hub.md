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

This repository publishes two independently versioned metadata artifacts:

- A **discovery catalogue** with **$catalogue_datasets dataset entries** from
  ISTAT, Eurostat, OECD, ILO, DoveVannoINostriSoldi (DVNS) and Cruscotto Italia.
- A **verified availability index** with **$availability_combinations joint
  combinations across $availability_datasets datasets**, built from complete
  source responses within the explicitly declared scope.

Neither archive contains observation values. The availability index adds evidence
about existing source datasets; its combinations are not additional datasets.
Neither archive includes search vectors or credentials.

## Browse the tables

The viewer exposes three explicitly configured subsets, each with a `data` split:
`catalogue` (all discovery entries), `availability_datasets` (indexed dataset
scope and evidence expiry), and `availability_combinations` (all indexed tuples).
These are metadata tables, not training examples or observation values.

Viewer tables are derived from the exact archives linked below. Nested metadata
is retained as JSON text so differing provider fields do not change the table
schema. Catalogue entries also retain their complete original row in `record_json`.
See [viewer integrity and source hashes](viewer-manifest.json).

## Verified availability

Snapshot: **$availability_taken_at**. Completed indexing partitions:
**$availability_partitions**.

| Provider | Dataset | Observed years | Distinct territories | Combinations | Evidence expires (UTC) |
| --- | --- | --- | ---: | ---: | --- |
$availability_rows

COFOG covers the geographies returned by DVNS for each indexed year, including
countries and European aggregates. Aggregates must not be added to their members.
OpenCivitas coverage is limited to **Calabria, Lazio and Lombardia**. Its separately
named annual datasets retain their distinct source contracts; they are not
automatically comparable or additive. These scopes do not cover every dataset,
region, municipality or year in the discovery catalogue.

The index preserves actual period/territory/dimension combinations and source
receipts. `observed`, `missing` and `suppressed` are distinct; observed zero is
not missing. Numeric values must be acquired from the original source after
selection and confirmation. Consumers must reject expired evidence and changed
source definitions. The expiry limits use for new selections; it does not delete
this reproducible historical artifact.

See [the index contract](availability/README.md),
[declared scope](availability/scope.json) and
[independent validation](availability/quality.json).

[Download the pinned availability archive]($availability_url).
Size: **$availability_bytes bytes**. SHA-256: `$availability_sha256`.

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
