# Verified observation availability

This index records joint combinations reported by the original providers. It
contains no measurement values and does not add new datasets to the discovery
catalogue. Its coverage is exactly the request grid in `scope.json`.

Snapshot: **$taken_at**. Completed partitions: **$partitions**.
Joint combinations: **$combinations**.

| Provider | Dataset | Evidence expires (UTC) |
| --- | --- | --- |
$dataset_rows

All declared partitions passed independent archive and exact-scope validation.
`quality.json` records the checks. Presence is explicitly `observed`, `missing`
or `suppressed`; observed zero is not missing. Labels retain source identities.

`availability.tar.gz` contains `manifest.json`, `datasets.jsonl`,
`partitions.jsonl` and `combinations.jsonl`. The archive is **$bytes bytes**,
SHA-256 `$sha256`.

Pin downloads to this repository's full commit hash and verify the digest.
Consumers must reject expired evidence and changed source definitions. The
index certifies the recorded responses; it does not establish a stable snapshot
of the upstream source or authorize resumption across source changes.

This artifact has its own manifest and checksums. It does not certify or replace
the separate discovery catalogue. Source rights remain those of each original
dataset; the index does not grant additional rights to measurement values.
