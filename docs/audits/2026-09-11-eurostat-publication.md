# Verified Eurostat availability publication

The four-series Eurostat availability index and its README are published at
immutable Hugging Face revision
`8cf8d9de59eaf3d9873379d027ffe3283f878ca0`. Every uploaded file passed the
publisher's immutable size and SHA-256 readback. This is an availability
publication, not a new discovery release or an installed consumer.

The archive is **8,892 bytes**, SHA-256
`74d7d37b2d0eb8cb829b9ef3179ecc00a1b7d0bdb04aac3d0a349d9dc6b3fc57`:

[Immutable Eurostat archive](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/resolve/8cf8d9de59eaf3d9873379d027ffe3283f878ca0/availability/eurostat-series/availability.tar.gz)

The producer was the clean, committed and pushed `c05c56e54cce92619279715745c89111d08c7ab5`.
Its complete suite passes 129 tests in 24.195 seconds. The exact projection core
remains `6b139e06612bee6e5cc9dd4594599b1f6c164654`; the publication command repeated
the [offline provenance qualification](2026-09-11-offline-eurostat-provenance.md)
before uploading.

## Scope and clocks

There are four datasets, ten partitions and sixty combinations. Only the four
dataset definition digests and the real assembly timestamp differ from the
previous index. Partition and combination tables remain byte-identical; the
source receipt clocks and expiry are unchanged. The earliest expiry is
**2026-09-11T07:54:50.517534Z**. Offline verification is not a new source read.

Exactly eight paths under `availability/eurostat-series/` were uploaded:
`availability.tar.gz`, `manifest.json`, `quality.json`, `scope.json`,
`inventories.json`, `SHA256SUMS`, `README.md` and `offline-provenance.json`.
The README declares attribution, the transformation and the original clocks.
The proof links original input hashes, short native graph receipts, the exact
implementation and observed runtime. Native XML, CSV measurements and the
private source pack are outside this publication.

## Local review and execution receipts

All operational files are retained under the ignored, durable directory
`build/eurostat-publication-20260911/`:

- `publisher.toml`, SHA-256
  `990510c762165311b191dd6629d289d99c75c3286cd7ba869c321fccedd14e61`;
- `README.eurostat-availability.md`, SHA-256
  `d77acd29a81c860b00478271a2ec84e4de8f701e7169ab03f5c39937d4c91fc7`;
- `root-validation.json` and `root-preparation.json`, recording the independent
  root check and eight staged file digests;
- `reviewed-publication/`, whose rendered README exactly matches the reviewed
  `Eurostat.README.proposed.md`;
- `publication-build/offline-publication-je4cm7py/`, containing the actual
  upload output and final per-publication receipt;
- `eurostat-publication.json`, with the immutable revision, archive digest,
  size, URL and `verified: true`.

The first sandboxed launch failed DNS resolution at the first HF connection,
before uploading. Its staging directory is retained separately as
`publication-build/offline-publication-f0toctjt/`. The authorized invocation
completed upload and readback. No native source request or publication-database
mutation was used in either invocation.

## Remaining adoption and documentation work

Consumer activation and the live metadata-context check are separate gates.
The root Hub card and viewer still refer to the preceding documentation release
`c2eae1ea79ea39a2ad9c07c0a416da152bae2a6f` at this checkpoint. Their preparation
exposed a contract error: the current strict inspector rejects the existing
schema-1 discovery archive before the documentation path can describe it.
An explicit, pinned historical-publication evidence path is being qualified;
new-export admission remains strict. The historical discovery errors and policy
must remain attributable, without claiming a new schema-2 evaluation.

The previous updater first-start deadline has already passed. This publication
does not extend the national/SSN evidence, install a timer or change running
main/Bandi services. Those release gates remain open.
