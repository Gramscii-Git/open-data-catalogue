# Explicit native child environment

The publisher passes `--env-file` to SDG, whose settings loader gives process
variables precedence over that file. Inheriting the invoking shell therefore
allows an unrelated `DATABASE_URL`, `OPENDATA_PACING`, `HTTP_HOSTS` or
`AUTH_TOKEN` to replace the declared deployment setting.

Publisher configuration schema 3 requires `deployment.process_environment`.
Native harvester and offline-projection commands receive exactly this validated
string mapping plus the publisher-owned `PYTHONPATH` for their declared source
roots. The mapping cannot override `PYTHONPATH`. An intentional process-setting
override must be declared in the mapping; the native environment file remains
unchanged. The selected core remains responsible for validating all seven
shared-pacing fields and the nested TCP keepalive policy.

The schema, example, both callers and dependent tests change together. Archived
configuration and running services are not changed. No admitted current native
publisher deployment exists to upgrade in this scope; its environment and shared
caller coordination must be configured explicitly before collection.

## Local verification

The tested change is based on `d894cb9` on `plugin/opendata`. Verification uses
macOS and the independent CPython 3.13.12 publisher environment under
`build/hf-publication-review-20260912/python-env`, with separate temporary and
cache directories under `build/harvester-environment-20260912`.

- Two real subprocess regressions first failed with inherited shell values.
  Their child is a local CLI protocol fixture: it observes the actual process
  environment and unchanged synthetic environment file without importing SDG or
  contacting a provider.
- `python -B -m unittest discover -s tests -v`: **166 passed**, 36.368 seconds.
  The unchanged publisher process owner ran the suite and closed normally. The
  retained `tests.stderr` SHA-256 is
  `4ecaefb01d29f3fdd0d7b511f1a898823d219d89b6b048e07b4f01302d559fb9`.
- The first following lint invocation failed. Its receipt remains incomplete.
  The mapping type error is corrected to `TypeError`; lint explicitly targets
  the repository's supported Python 3.11 minimum so `tomllib` is recognized as
  standard library.
- After that correction,
  `python -B -m unittest discover -s tests -p test_harvester_environment.py -v`:
  **4 passed**, 0.103 seconds. This includes missing/invalid mapping rejection,
  hostile parent settings and an explicitly declared process override.
- `ruff check --target-version py311` passes for `catalogue/cli.py`,
  `catalogue/config.py`, `catalogue/availability_offline.py`,
  `tests/test_harvester_environment.py`,
  `tests/fixtures/harvester_environment.py`, `tests/test_release.py` and
  `tests/test_runtime.py`. `git diff --check` passes.

No native SDG collection, provider request, live database modification, runtime
admission or dataset publication is part of these tests. Other operating systems
are not qualified by this local run.
