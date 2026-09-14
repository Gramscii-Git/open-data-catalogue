# ISTAT collection and publication checkpoint

This is an operational checkpoint, not a completed publication. Times below are
observations on 14 September 2026 in Europe/Rome unless an explicit offset is
given. Credentials and generated evidence remain outside Git.

The [standalone collection checkpoint](2026-09-14-standalone-collection.md)
records the subsequent completion of run 13, explicit failures and the
launchd-owned structure continuation with request backoff.

## Saved code

- Publisher: `c0995168230ea98dd037ad833061d45272bbe6d5`, already on `main`.
- Native registry synchronization: SDG commit
  `7c79dcae5651ced43f699f029a4b30f448b33b05`, merged through
  [PR 156](https://github.com/Gramscii-Git/semantic-deterministic-graph/pull/156)
  as `0a3d2a24f4edf04fd78d5d1a895e3aa3fb1e008e`. Their source trees agree.
  The change passes 57 existing focused tests and 12 new CLI/worker regressions,
  Ruff and diff checks. Owned verification databases are removed.
- Subsequent DVNS rights work is on SDG `plugin/opendata`: evidence checkpoint
  `5b21fc2c` and implementation `cf98e889`. The implementation passes 84 focused
  tests and Ruff. These commits do not change the running collector's source.

## Actual collection state

The collector uses a clean detached SDG checkout at `7c79dcae`, the publication
database, and one shared ISTAT admission bucket for hub, REST and metadata.
The interval is 13 seconds. Two admissions measured at 01:08 were 13.004351
seconds apart. ISTAT's [published limit](https://www.istat.it/en/classifications-and-tools/sdmx-web-services/)
is five queries per minute per IP. Every other caller on this egress must share
the same admission contract or remain paused.

Native run 13 starts at `2026-09-13T23:08:40.972634+00:00`. The complete registry
is reconciled at `2026-09-13T23:09:31.761833+00:00`:

- ISTAT now has 4,908 catalogue records; three still lack a licence.
- `742_1142_DF_CPI_INNOVDIG_3` is active, searchable and served, with
  `retired=false`. This proves catalogue admission, not a completed observation
  download or a successful Bandi workflow.
- At 01:18:21, 41 metadata reports have an attempt in this run, 33 have a new
  successful fetch and eight have an error. A subsequent read identifies nine
  explicit HTTP 500 `Report not found` responses. These are source failures,
  not evidence of an IP block. The run remains in progress at this checkpoint.

The job is owned by the current command session, not by an installed scheduler.
Do not assume it survives closing its owner. The native implementation commits
registry state and individual report results; inspect those records before
resuming. Never start a duplicate collector or delete its publisher lock.

## Persistent local inputs

In the publisher checkout, `build/istat-resumption-20260913/` contains:

- `publisher.current.toml`, SHA-256
  `6b1843eec716af62191886812728e3508fa116e07d44471c635b715fe441f3d6`;
- `private/registry.enabled.env`, private deployment settings;
- `harvester-7c79dcae/`, the immutable native source;
- `run_harvester.py`, which loads the publisher configuration, acquires its
  native lock and delegates to the owned harvester command;
- `sync-registry/stdout-authorized.log` and `stderr-authorized.log`;
- source readbacks, licensing evidence and the retained availability-release
  manifest in `hf-publication-inputs-20260914/documentation-releases.json`.

The configured document contract is
`1100224ca60494886656eed08109cf862cff22bd6b47b7cda7783d045a484b20`, measured
with this native source. The older `a405b301...` contract does not match.
The configured Python environment currently resides under `/private/tmp`; if
it is unavailable, rebuild the pinned environment and validate a new deployment
configuration before running. Do not silently substitute another checkout.

`build/recovery-20260914/main-database.dump` preserves the main-service backup
outside `/private/tmp`. It contains 545,063,337 bytes with SHA-256
`c407525740b4cf42f19cf5f42c8a77d07820efa9f4e9d9c274b99a70c6016525`.
The APFS clone is verified against the original. The private backup is not a
catalogue export and must not be uploaded to Hugging Face or GitHub.

## Resume in this order

1. Inspect the existing collector owner and `public.opendata_runs`. Allow a
   healthy owned run to finish. An interrupted run requires explicit ownership
   reconciliation before another writer starts.
2. After registry/report synchronization, remeasure pending structures and the
   exact Bandi dataflow. Use native `structure --provider istat` with resume
   enabled; use `--dataset` for an explicit target. Do not apply `--patience`,
   force lifecycle flags or clear the complete backlog with `--no-resume`.
3. Restore the main service through its managed, verified successor. The 9100
   service is stopped and disabled during maintenance. Its backup and inventory
   exist; production migration and successor startup are not completed. Bandi
   owns the separate 9110 cutover. Keep shared source access coordinated.
4. Regenerate documents with native `enrich` using the verified local embedder.
   The last export fails explicitly on the undeclared Italian document
   `eurostat:ILC_LVHO06:it`. Existing stopped embedding endpoints are not a usable
   deployment. Resolve the document contract; do not relax publication gates.
5. Resolve the remaining source-rights and structure defects, then use the
   existing publisher commands below. Their quality checks are mandatory.

From the publisher checkout, with the validated configuration present:

```sh
python3 ./update --config build/istat-resumption-20260913/publisher.current.toml prepare
python3 ./update --config build/istat-resumption-20260913/publisher.current.toml publish
```

`publish` validates again and uploads the discovery archive, manifest, quality
report, checksums and generated dataset README together. Completion requires its
immutable-commit readback and `publication.json` with `verified=true`. Then run
the documented `publish-documentation` command with the actual archive/revision
and the retained availability manifest to regenerate the combined Hub card.
Historical availability timestamps and expired coverage remain historical.

The last confirmed Hub change is README-only commit
`f3930bb41012ae41d68902f171389ec09afec290`. This checkpoint does not attest a new
dataset upload. The exact 105 Eurostat/OECD historical rights cases remain
unresolved; EPEA needs an upstream rights declaration and remains excluded from
observation acquisition. General provider terms do not resolve individual
exceptions.

The publisher is ordinary Python and does not call Codex or OpenAI models.
Running it independently does not consume Codex tokens. `schedule` only writes
a launchd definition; generation does not install or start it. No automatic
publication job is installed by this checkpoint.
