# Published artifacts and update admission

The September 12 readback of the HF repository identifies revision
`6c7fa70bbe1e3dd7a7f456e62aad346742866816`. The README and three public reports
match the retained publication receipts exactly. This is a metadata readback;
it performs no new acquisition or catalogue quality evaluation.

| Published artifact | Immutable revision | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Discovery archive | `8854722f8a035cbed57b1cb2bbbed4a297f5c188` | 55,034,326 | `1e9eafeb4e691dc810d0de73fe387098b5029fcb740934d2fd4eb4ada56864e9` |
| National availability | `fc82d7bd8154da355a45a81d772615306413fdc9` | 50,882,306 | `6daac1bf6aa8cdb8087440b75ccba01aacec197659ffefd45b8d4fbbf0b710e6` |
| SSN history availability | `8d71a4fb549a233b4471cee4b0e0b3f53997dd2e` | 1,976 | `dfa567b92fc6d4cb6aea30b7e0c5a8f32864d2ed476a2673b5c062df7b781360` |
| Eurostat series availability | `8cf8d9de59eaf3d9873379d027ffe3283f878ca0` | 8,892 | `74d7d37b2d0eb8cb829b9ef3179ecc00a1b7d0bdb04aac3d0a349d9dc6b3fc57` |

The archive identities above come from the immutable published card and retained
publication proofs; this review does not download or revalidate their row bodies.
The discovery snapshot is dated September 7, contains 15,990 catalogue entries
and declares schema 1. Its published status remains `admitted: false` and
`current_quality_evaluation: not_performed` under the schema-2 requirement.

The three availability indexes contain 35 datasets and 911,795 combinations.
All 35 evidence expiries are on September 11, between 07:53:52.035944 and
08:11:37.364978 UTC. They therefore provide no unexpired selection evidence at
this review. The original timestamps, data hashes, recorded source licences and
quality defects remain unchanged. The four Eurostat series and the declared
national/SSN scopes do not establish all-provider or all-dataset completeness.

## Integration boundaries

Publisher source `33fc2a42da4fe527064b6cc67c0672779e5abe83` already exposes the
explicit `run-update` sequence for build, publication, immutable readback,
activation and card/viewer publication. Its update plan schema is 3; state schema
2 requires actual publication, activation and discovery-readback receipts.
Availability publication and activation reject expired evidence. Documentation
can describe historical artifacts without granting them current admission.

The retained September 11 publication configuration is schema 1 and is not a
current operational configuration. The separate deployment-adoption record is
also incomplete. Neither is authority to start a new collection or timer.
An operational update still needs the current declared harvester environment,
shared pacing authority, active consumer pins and real source results. No such
adoption or fresh dataset release is claimed by this documentation change.

The publisher's kernel-held lock file persists after execution. Removing that
file can create competing lock inodes; the README requires inspecting owner and
phase evidence while retaining the file. The execution forecast is not a work
deadline. These corrections align the instructions with the existing code.
GitHub Actions remains disabled; no workflow or scheduler is introduced.

The boundaries checkout is clean on `main` at
`3d672cbd6c356c11266a34b4e39de4de6468f847`. Its build declaration and README
already separate historical municipality inventories, shape vintages and
dataset-specific joins. Catalogue metadata changes alone do not justify a
geometry rebuild. No newly qualified geographic source or incompatible join is
established by this review, so boundary code and assets are unchanged.

## Evidence and verification

The ignored `build/hf-publication-review-20260912/` directory retains the public
repository response, HTTP headers and four immutable files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `README.published.md` | 29,571 | `53024936e2d2fd0a2942c1e1d293cc4e32e920826292c327b43bc75cc9d70843` |
| `catalogue-quality.json` | 4,088 | `20d677c935c52c404092d160a9debae0abb09a53f0ef5eab3db1f86983b86125` |
| `catalogue-status.json` | 2,271 | `106dbcc898c01c06e14eda37121f3bf37ababf7a65c9cb1dc3d9da19b0ac6b57` |
| `viewer-manifest.json` | 2,277 | `39fa399822b25f52a12225b2fbeaa1264342b66c6a1bac24230bb0fb754e1aa0` |

Verification for this documentation-only change consists of immutable byte/hash
comparison, source/contract and reference review, unchanged template placeholder
inventories and `git diff --check`. No unaffected runtime suite, provider read,
database operation, model, service or archive copy is part of this review.
