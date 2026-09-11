# Native lifecycle authority in descriptive document proofs

A dataset with a qualified native metadata-only role can supply descriptive
catalogue documents while remaining unavailable for observation acquisition.
The publisher independently checks the same selected input that the core uses
for rendering and proof generation. A retained legacy observation structure is
preserved in the archive but is not an input to this descriptive projection.

This change requires **document contract schema 2**. Discovery archive schema 2
and publisher handshake schema 2 retain their existing versions. Every provider
must explicitly declare its source-role mode; there is no admission path for a
missing role declaration or document contract schema 1.

## Evidence boundary

Registry roles require a present lifecycle membership bound to the complete
native registry receipt, exact agency/dataflow/version identity, original source
clock, declared queryability and the provider's excluded structure references.
Native names, descriptions and ordered annotations, including duplicates, become
the descriptive input. Missing native language titles remain missing even when
historical catalogue fields contain a title. Unserved rows without the required
lifecycle evidence are rejected, including when no legacy structure is present.

Licence values and retained structures are not replaced or newly qualified.
Neither this verifier nor its tests updates the publication database. The real
81-record ISTAT reconciliation plan is separate and must retain all requested
documents and its four missing-language errors. This checkpoint does not qualify
that plan or the overall release.

## Independent core-to-publisher check

Core commits `ee5fe5e2` and `c9fc4031` implement the document-input boundary.
Their audit is
`semantic-deterministic-graph/docs/audits/2026-09-11-opendata-native-document-roles.md`.
The final check used core `c9fc4031c06feaf3dff4df7aff84982e0f79c537` and this
publisher worktree based on `c05c56e54cce92619279715745c89111d08c7ab5`.

The core's mounted API and snapshot tests produced an actual seven-table archive
from an isolated synthetic contract fixture: one metadata-only catalogue row,
its retained legacy structure, and two documents. Its lifecycle receipt covers
the complete six-record fixture registry. This is a contract test, not evidence
of source-wide coverage or release quality.

The independent publisher inspected the archive without importing the core,
opening a database connection or issuing a source request. It found no missing,
undeclared or invalid document projections and no issues.

| Artifact | SHA-256 |
| --- | --- |
| Final core archive | `af756360577af61a462037684fb854430fa5b267c9461725f7cfd36dc1faf516` |
| Final document contract | `2af2f7a6e8b5947985dfd67ded8d446dc9568361f6a58f1b6004bf72ddeea8c8` |
| Independent readback receipt | `b5de96224d1bedb86c0636f0ab4580ae31fed8d0152b2c87a1a486a6dc0650c8` |
| Retained regression fixture | `db86b5c022b66eca4bc715e20c581ea817b4a68d4335094e299ae89154ae7a95` |

The final archive is
`/private/tmp/sdg-metadata-role-c9-gate-20260911/test_snapshot_roundtrip_preser0/metadata-only.tar.gz`.
The independent receipt and executable check are
`/private/tmp/sdg-opendata-metadata-role-c9-publisher-readback-20260911.json`
and the sibling `.py` file. The receipt records the tested publisher file hashes,
all table counts and both exact source/text projection digests. The contract pin
belongs to the frozen core/configuration; a combined checkout must derive and
verify its own pin when renderer inputs change.

The committed compressed regression fixture preserves an earlier actual export
from `ee5fe5e2` (archive SHA-256
`fe08763969996650f118fb5edb973584e1a82c639e52d0cb8fcc382d0528b499`).
It is intentionally not regenerated to hide version changes.

## Verification

On macOS 26.6.2 arm64 with Python 3.13.12:

- `python -m unittest discover -s tests -v`: **139 passed**, 23.710 seconds;
  `/private/tmp/opendata-document-role-final-python313-20260911.log`.
- `python -m unittest tests.test_document_roles -v`: **10 passed**. The tests
  exercise absent evidence, queryability conflicts, incomplete inventory counts,
  altered annotations, absent native language, undeclared configuration, wrong
  contract version and illegal acquisition promotion.
- Final core `test_opendata_metadata_role_api.py`: **2 passed**, 5.30 seconds,
  through the real mounted catalogue API and snapshot round trip;
  `/private/tmp/sdg-opendata-metadata-role-c9-api-20260911.log`.
- Ruff on all changed Python files with the core's explicit
  `server/pyproject.toml` configuration, and `git diff --check`: passed.

Core qualification additionally includes 144 focused document/inventory/parser/
catalogue tests and the four retained Eurostat definition/context readbacks.
All four Eurostat definitions and their availability contexts remain unchanged;
the source receipt is
`/private/tmp/sdg-eurostat-metadata-role-readback-20260911.json`, SHA-256
`cb3439a1fceeccbf19cb6bb0ab93b10851a7599b9afb1caf58a16e696e19c21e`.

The combined integration suite, actual reconciliation of the 81 records and
release-wide document admission remain separate gates. This checkpoint changes
no production prompt, model, source licence, publication database or remote data.
