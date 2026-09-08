---
pretty_name: Open Data catalogue
license: other
license_name: per-dataset
language:
  - it
  - en
---

# Open Data catalogue

Metadata and searchable descriptions collected from public-data providers.
Observations are not included: obtain numeric values from the original provider.
Search vectors are not included: build an index with the reader's own embedder.

## Release

Snapshot time: **$taken_at**.

| Table | Rows |
| --- | ---: |
$table_rows

| Provider | Datasets |
| --- | ---: |
$provider_rows

## Quality

The release passed the explicit policy recorded in `quality.json`. Passing that
policy is not a guarantee of complete provider coverage or source-data accuracy.

| Check | Recorded count |
| --- | ---: |
$quality_rows

## Reading

The archive `$archive` contains seven JSONL tables and `manifest.json`.
Each JSONL line is one database row. Dates retain their recorded time zones.
Provider identifiers and dataset keys are preserved. No credentials are included.

Archive size: **$bytes bytes**.

SHA-256: `$sha256`.

Select this dataset repository's full commit hash when downloading files. A branch
name is mutable and must not be paired with a fixed digest as a permanent release
address. The publisher writes the verified commit URL to its publication receipt.

## Rights and provenance

Source terms are retained in each catalogue row's `licence`, `attribution` and
`sources` fields. The compilation does not replace or expand provider rights.
Consult the original provider's terms before reuse. Missing metadata is reported
by the quality checks, never replaced by an assumed licence.

Gramscii's assembly and its added documentation retain the compilation's
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) terms. Those terms cover
Gramscii's contribution, not an expansion of rights to the underlying sources.

## Related projects

- [Publisher and release policy](https://github.com/Gramscii-Git/open-data-catalogue)
- [Harvester](https://github.com/Gramscii-Git/semantic-deterministic-graph)
- [Geographic boundaries](https://github.com/Gramscii-Git/boundaries)

Map joins require matching code systems and territorial vintages. Coverage of
every catalogue identifier by the boundaries repository is not guaranteed.
