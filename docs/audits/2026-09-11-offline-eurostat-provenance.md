# Explicit offline Eurostat producer provenance

The publisher now has an explicit SDMX offline validation and publication path.
It reuses the current SDG graph, constraint, CSV and availability projectors;
it does not change the consumer archive schema or HTTP replay. Native graph
receipts remain separate original inputs. No dispatched request digest, response
header, observation period or source freshness is synthesized.

`check-offline-availability` validates a digest-pinned input manifest and makes
no upload. `publish-offline-availability` repeats the whole validation before
any remote effect. The ordinary publisher rejects an offline proof marker unless
its explicit verified publication path supplied the proof pin. All ordinary
archive, exact-scope, inventory, source clock and expiry checks still run.

## Qualified native inputs and code

The reviewed candidate is 8,892 bytes, SHA-256
`74d7d37b2d0eb8cb829b9ef3179ecc00a1b7d0bdb04aac3d0a349d9dc6b3fc57`.
The original archive remains
`b1c91bdd4ecc2b4cc89389f8ad471d5c1d00dc68abdccb43c59819a3199cc9fc`.
Both archives contain four datasets, ten partitions and sixty combinations.

The durable input manifest is
`/Users/robertomarras/progetti/open-data-catalogue/build/eurostat-publisher-proof-20260911/provenance.json`,
SHA-256 `7d96b2c7c8788fbe75a2312a361ade6f6d20565fdc7fa907b64299276d4bd8dc`.
It binds original/candidate archives, exact scope and inventory evidence, three
configuration files, the sealed original 33-response capture, four native graph
bodies/short receipts, four old/new definition hashes and an explicit deadline.
All assets have relative paths, byte counts and content hashes. The configured
availability policy bounds individual and aggregate input bytes.

The exact core is `6b139e06612bee6e5cc9dd4594599b1f6c164654`, in the separate
`/private/tmp/sdg-eurostat-proof-core-20260911` worktree. This identity was not
silently replaced by a later integration commit. The validator checks all
262 Python files under `server/sdg` against the declared manifest, actual commit
blobs and filesystem. It checks the origins and hashes of all 84 imported SDG
modules. A modified module with an adjusted manifest still fails when its code
is absent from that commit. Unrelated ignored assets do not invalidate the code
identity; imported SDG modules outside the declared core fail explicitly.

The actual verification runtime records CPython 3.13.12, lxml 6.1.3,
pydantic 2.13.5, pydantic-core 2.46.5, PyYAML 6.0.3 and httpx 0.28.1, with
libxml 2.14.6 and libxslt 1.1.43. The actual project lockfile matches its commit,
SHA-256 `ec627295b826b725d5c7f8d6a80e7dd2ac1f571565b04ef465eded42d4ea2e9d`.
This records the observed environment; source and lockfile hashes alone do not
certify identical behavior on another installation.

## Verified result and refusal gates

All four definitions were reconstructed from the original catalogue, exact
native dataflow/DSD graphs, complete referenced domains and Actual constraints.
All sixty combinations were independently projected from the ten retained CSV
responses. Partition and combination tables are byte-identical to the original
archive. Dataset changes are confined to the declared definition hashes;
`verified_at`, `valid_until`, scope and all source receipts are unchanged.
The only other permitted difference is the real candidate assembly time.
The earliest expiry remains **2026-09-11T07:54:50.517534Z**.

The retained native gate tried three deliberately invalid copies:

- A candidate with a false definition digest and an adjusted manifest was
  rejected by the actual graph projection.
- A resealed graph receipt naming a different native agency was rejected before
  treating its body as the exact source response.
- A modified CSV body was rejected against its pinned original capture.

Every negative case failed before a publication staging directory was created.
The positive case prepared eight validated files without upload. The result is
`/Users/robertomarras/progetti/open-data-catalogue/build/eurostat-publisher-native-gate-final-20260911/result.json`,
SHA-256 `c01d79e86761e38a3bce2622f6a3ff6505dfd447e6b57b4372289bc389a75797`.
The copied validation proof in the input bundle is `verified-provenance.json`,
SHA-256 `02010e319a904185f2029c0b2da3b46e893d06574afbb455d9970d4981837f9a`.

The complete local publisher suite passed **129 tests in 24.195 seconds** with
Python 3.14.6 on macOS arm64. Focused tests cover tampering, incomplete graph
sets, source clocks, TTL extension, changed coordinates, expired evidence,
commit/blob mismatch, untracked Python and foreign imported modules. The first
full-suite rerun was blocked by sandbox loopback-bind permissions; the authorized
rerun passed. Its log is
`/private/tmp/opendata-offline-provenance-20260911-full-tests-authorized.log`.
Ruff and `git diff --check` pass. No consumer models, live sources, PostgreSQL
publication database or remote CI were used for this tranche.

## Future publication boundary and retained rights

A future operator command would use the explicitly reviewed manifest and
`--destination availability/eurostat-series` in
`Gramscii-IT/open-data-catalogue`. It would upload only:

- `availability.tar.gz`
- `manifest.json`
- `quality.json`
- `scope.json`
- `inventories.json`
- `SHA256SUMS`
- `README.md`
- `offline-provenance.json`

The proof binds the candidate, original index, input manifest, native input
hashes, graph URLs/times, exact core and observed runtime. It contains no graph
XML, CSV values, complete captured HTTP headers, credentials or local absolute
paths. Publishing hashes and short receipts does not publish the source bodies.
The supplied destination is separate from discovery and does not activate a
consumer pin. This tranche performed neither publication nor activation.

The metadata index retains the exact previously published labels, periods and
combinations; it adds no measurement values. The original index README states
that source rights remain those of each dataset and grants no additional rights.
The configured source notice is the Eurostat reuse policy. The existing
[retained-rights audit](2026-09-10-retired-licences.md#eurostat-actual-historical-withdrawal-and-distribution-level-rights)
records a successful capture of that notice with dataset/third-party exceptions;
it must not be represented as an unconditional new grant. The publisher's MIT
licence covers its software and associated documentation, not an invented
licence for Eurostat observation bodies. A future publication review must retain
that distinction; this validation does not authorize raw-source publication.

All 82 pinned native input files, original archives and receipts remain in the
local input bundle. `source-pack.tar.gz` additionally retains the verification,
native gate and exact committed core source/lockfile archive: 87 files,
4,616,521 bytes, SHA-256
`a985840db63d909ab2f36c46243b9b71e31c6e3b13511df24d2fdb141dc1d0b6`.
`source-pack-receipt.json` lists every file hash. This source pack is private and
is not in the upload list. Installed third-party binaries are not included;
their observed versions are recorded separately.
