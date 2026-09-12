# National availability publication, September 10, 2026

The national availability archive and licensed Cruscotto source snapshots are
published and independently read back at immutable Hugging Face revisions.
Activation succeeded in an inactive SDG checkout. This audit does not certify
installation in a running chat deployment or completion of other provider scopes.

## Artifacts and verification

| Artifact | Immutable revision | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| [National availability](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/resolve/fc82d7bd8154da355a45a81d772615306413fdc9/availability/availability.tar.gz) | `fc82d7bd8154da355a45a81d772615306413fdc9` | `6daac1bf6aa8cdb8087440b75ccba01aacec197659ffefd45b8d4fbbf0b710e6` | 50,882,306 |
| [Cruscotto snapshot manifest](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/resolve/eaeeae1eca695583e2e4c1ae6fa956fd13c05023/source-snapshots/manifest.json) | `eaeeae1eca695583e2e4c1ae6fa956fd13c05023` | `b2c2b5ef99136b363aff3259f6725b1ef36a724e88cb6ba2bc4ecbd78d42e1ae` | 1,269,379 |

The archive contains 911,670 combinations, 30 datasets and 197,471 completed
partitions. Five DVNS datasets and 25 Cruscotto domains are included. The snapshot
manifest binds the exact availability digest and dataset definitions to 7,896
native responses in 256 shards. Every uploaded file passed size and SHA-256
readback. Availability contains selection metadata; licensed snapshots preserve
the projected source values and attribution.

The original scan finished at `2026-09-10T12:46:14.180869+00:00`. Its 8,206
retained response/receipt pairs were sealed under capture SHA-256
`98bf4f08f04acb7ee42348e20e00e2de4a7930ac8773a424d0fda2519bbc1094`.
The completed 25-domain replay reported `received_bytes: 0` and finished at
`2026-09-10T13:01:58.190063+00:00`: no new provider observations or inventory were
requested. The archive build time is `2026-09-10T13:01:58.209197+00:00`.

The resolved scope input SHA-256 was
`209239e5b37a5f5eff73b8a35cbb6df130a7461ac41c401848326c56fb7082bb`;
the retained inventory input SHA-256 was
`eb0decd8e5f8a894fb02113d8d52aa32ad1c732795acda4495b0afad1d20c1e2`.
Publication serializes these JSON documents independently; their published byte
digests can differ while preserving the verified source content and bindings.

## Source universe and ANNCSU

The [published inventory evidence](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/raw/fc82d7bd8154da355a45a81d772615306413fdc9/availability/inventories.json)
records 7,896 distinct six-digit codes returned by the Cruscotto lookup endpoint
`https://cruscotto-italia.dati.gov.it/data/lookup/comuni-index.json`.
Retrieval was `2026-09-10T07:56:02.502421+00:00`; HTTP Last-Modified was
`Sat, 05 Sep 2026 02:00:05 GMT`. The source body is 729,436 bytes with SHA-256
`9ed48967b1dc33e44f9c3adf2897fa050990c0501ccf00b6226b489b5d6466ff`.

This is the universe of this provider release. Retrieval and HTTP modification
times do not establish its administrative vintage or today's Italian municipality
count. Current territorial identity and map geometry require separate dated
mapping evidence. This release does not modify the boundaries repository.

ANNCSU contributes 23,670 combinations: `n_strade` and `n_civici` in counts, plus
`pct_geo_ref` in percent, across 7,890 source municipality codes. Six completed
municipality responses contain no ANNCSU observations. Completed acquisition
therefore does not imply that each domain reports measurements for every code.
The codes without ANNCSU observations are `018082`, `024027`, `024071`, `071029`,
`082017` and `111099`, verified against the complete imported partition and
combination tables; `anncsu-coverage.json` retains the local census.
The snapshot manifest records CC BY 4.0, attribution to Agenzia delle Entrate and
ISTAT, the official ANNCSU source URL, and the permitted `civici_anncsu` field.
Its dataset definition SHA-256 is
`0108035aef53e35ae6490ae912fbf36ffd69bdc2245435b400800bff1c530a31`.

Original evidence dates remain unchanged. DVNS evidence expires at
`2026-09-11T07:56:10.800808+00:00`; Cruscotto evidence expires at
`2026-09-11T08:11:37.364978+00:00`. The configured lifetime is 24 hours from the
oldest source receipt. Replay and upload do not renew it. Snapshot times are
source photographs, not inferred historical observation periods.

## Isolated consumer activation

SDG commit `63643fe0` adds the explicit ANNCSU selection binding and the verified
national archive/snapshot pins. Atomic activation validated all 30 configured
datasets, their axes, evidence validity and exact snapshot definitions. The
imported SQLite database occupies 2,462,101,504 bytes. Existing SSN and Eurostat
index pins were preserved.

Activation occurred only in
`/private/tmp/sdg-opendata-national-activation-20260910`. The publisher checkout
is `/private/tmp/opendata-national-release-20260910`; its local release evidence
lives under `build/national-20260910/`:

- `capture.json` and `capture-receipt.json`: sealed retained responses.
- `availability-6p8r80uh/`: replay archive, scope, inventory and quality report.
- `snapshots-publication-msr0lxtq/publication.json`: verified source manifest pin.
- `publication-rdrgwffa/publication.json`: verified availability pin.
- `activation-d5g2iys9/activation.json`: successful consumer activation receipt.

The publisher's full local suite on the code committed as `4b4216c` passed:
94 tests in 20.956 seconds on macOS, Python 3.14.6. Ruff and `git diff --check`
passed. The consumer activation/status tests at `63643fe0` also passed:
17 tests in 39.34 seconds. Tests use isolated loopback
servers; native Linux and Windows qualification was not performed. Separate
authenticated publication and activation checks above used the real Hub bytes.

## Hub documentation and viewer

The [published Hub card](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/blob/c2eae1ea79ea39a2ad9c07c0a416da152bae2a6f/README.md)
and seven viewer tables were published at
`c2eae1ea79ea39a2ad9c07c0a416da152bae2a6f`. Every one of the ten publication files
passed size and SHA-256 readback. The README is 27,817 bytes with SHA-256
`113a5d846eec4f1052e50d6e22d9e0ef80bbec18c513048da7c43f394f16ac4c`.
It reports 35 indexed datasets and 911,795 combinations across the three
independent availability releases, preserving exact evidence verification and
expiry times. Period summaries remain bounded; full identifiers and calendar
bounds remain in the pinned archives and viewer rows.

The [viewer manifest](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/resolve/c2eae1ea79ea39a2ad9c07c0a416da152bae2a6f/viewer-manifest.json)
records every table's source archive digest, row count, size and checksum. Local
evidence is `documentation-bgihbtyc/publication.json` and
`documentation-bgihbtyc/viewer-manifest.json`, with the complete input set in
`documentation-releases.json`. All four input archives were verified against
their immutable Hub bytes before this documentation publication.

The seven-table discovery archive remains pinned to
`8854722f8a035cbed57b1cb2bbbed4a297f5c188`, with its recorded quality defects.
This availability release does not waive or repair those discovery quality gates.
The independently published SSN history and qualified Eurostat series remain at
`8d71a4fb549a233b4471cee4b0e0b3f53997dd2e` and
`5f6809f4a808de8618f046388a9ca4bea33477f1`, respectively.
