# Published catalogue evidence and current admission

The documentation operation must identify which quality evaluation it describes.
Discovery publication `8854722f8a035cbed57b1cb2bbbed4a297f5c188` declares snapshot
schema 1. The current export inspector requires schema 2 and document provenance.
Calling that inspector to regenerate a card for the existing publication fails
before it can return quality metrics. This is a distinct operation from admitting
a new export.

`publish-reported-documentation` requires explicit immutable archive and quality
report pins. It verifies the local bytes, report/archive identities, manifest,
historical policy and remote bytes before staging. It preserves the original
quality report byte for byte. A separately named status artifact binds both pins
to the configured current policy and its digest, declares the observed/required
schemas and records `current_quality_evaluation: not_performed`, `admitted: false`.
Schema 2 alone also cannot grant admission through this operation. The ordinary
export and documentation inspector retain their strict schema/provenance gate.
There is no recovery from an inspector error into the reported-evidence mode.

The status filename is explicit, must be a root JSON filename and cannot collide
with discovery `manifest.json`, `quality.json`, historical quality, viewer
manifest or publication receipt. The configured discovery archive must end in
`.tar.gz`, so it cannot be a status artifact. Rejected filenames fail before HTTP
or staging. All template placeholders are required.

Update plan schema 2 requires an explicit catalogue documentation mode.
`published_report` is restricted to retained discovery and must identify the
same verified archive as update state. Its immutable evidence is checked before
collection and when preparing documentation. No operational plan, timer, runtime,
quality threshold, source timestamp or database was changed by this work.

## Qualification

Code checkpoints are `c505272` and reserved-path correction `4bf752d`.
The complete publisher suite at `4bf752d` passed **142 tests in 30.909 seconds**.
The focused evidence/documentation/update suite before the reserved-path
correction passed **47 tests in 24.725 seconds**; the full final suite includes
that correction's negative cases. Ruff, compileall and `git diff --check` pass.
Tests use temporary directories and real loopback HTTP, including the updater's
publication/readback path. The first sandbox-only attempt could not bind local
ports; qualification used the authorized loopback run.

The actual preview was generated at `c505272` using the allowed filename
`catalogue-status.json`. Correction `4bf752d` only rejects additional colliding
filenames and does not change the preview's inputs or output semantics. The
preview read back immutable HF archive/report bytes and all three availability
archives. It contains eleven publication files and performed no upload.

Persistent evidence is under
`open-data-catalogue/build/eurostat-publication-20260911/`:

- `documentation-preview-reported/`: actual generated publication files.
- `documentation-preview-verification.json`, SHA-256
  `2cebf7133e8793fbd701de5396158ad4a2108e39361a23d08bc49903cc17b2cf`.
- `README.hub.complete.diff`, `viewer-manifest.complete.diff` and
  `catalogue-quality.complete.diff`: complete comparisons to HF
  `c2eae1ea79ea39a2ad9c07c0a416da152bae2a6f`.
- `publisher.reported.toml`, `published-catalogue-evidence.json` and
  `README.hub.eurostat.reported.md`: explicit successor inputs; the initially
  frozen configuration and templates are preserved.

Six of the seven viewer files are byte-identical, including all catalogue,
national, SSN and Eurostat combination rows. The remaining Eurostat dataset table
changes exactly four `definition_sha256` values. The viewer manifest also changes
the Eurostat source archive references to SHA-256
`74d7d37b2d0eb8cb829b9ef3179ecc00a1b7d0bdb04aac3d0a349d9dc6b3fc57`.
Its publication revision is `8cf8d9de59eaf3d9873379d027ffe3283f878ca0`.

The retained `catalogue-quality.json` remains SHA-256
`20d677c935c52c404092d160a9debae0abb09a53f0ef5eab3db1f86983b86125`.
Its historical metrics and caveats are unchanged. The README explicitly attributes
them to the original evaluation and discloses that the current document contract
has not been evaluated. This does not replace or qualify discovery `8854722`.

The proposed README is SHA-256
`53024936e2d2fd0a2942c1e1d293cc4e32e920826292c327b43bc75cc9d70843`.
The separate status is SHA-256
`106dbcc898c01c06e14eda37121f3bf37ababf7a65c9cb1dc3d9da19b0ac6b57`.
All existing discovery/national/SSN/snapshot pins and source expiries remain
unchanged. No source XML/CSV bodies are part of the documentation publication.
