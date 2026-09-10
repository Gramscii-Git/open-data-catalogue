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

## Published root card and viewers

The root card and seven viewer tables are published at immutable revision
`6c7fa70bbe1e3dd7a7f456e62aad346742866816`. The publisher reread all eleven files
and verified their sizes and SHA-256 digests. Root independently compared every
staged file to the reviewed preview; all were byte-identical.

[Immutable dataset card](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue/blob/6c7fa70bbe1e3dd7a7f456e62aad346742866816/README.md)
is 29,571 bytes, SHA-256
`53024936e2d2fd0a2942c1e1d293cc4e32e920826292c327b43bc75cc9d70843`.
The final producer `0d718e8` has the same code/tests as qualified `4bf752d`,
whose full local suite passes 142 tests. The explicit reported-evidence mode
is described in [its qualification audit](2026-09-11-retained-catalogue-documentation.md).

Six viewer files remain byte-identical to the previous publication; the seventh
changes only four Eurostat definition hashes. National, SSN and discovery
archive pins and source snapshots are preserved. The historical quality report
is unchanged. Separate `catalogue-status.json` states that no current quality
evaluation was performed and admission is not granted; documenting schema 1
does not qualify it as a new schema-2 export.

The actual operation is retained under
`publication-build/reported-documentation/documentation-ay38d1r8/`.
`documentation-publication.json` records `verified: true`;
`documentation-root-readback.json`, SHA-256
`4baefc0a098f6dd592fe83e1f8a8b1a687421f0a3751ff613b59f6a709bade44`,
pins all eleven preview/output digests. No native source request occurred.

## Remaining adoption work

Consumer activation and the live metadata-context check remain separate gates.

The previous updater first-start deadline has already passed. This publication
does not extend the national/SSN evidence, install a timer or change running
main/Bandi services. Those release gates remain open.
