# DVNS authoring scopes and chat selection qualification

These configurations declare work to build and publish. They do not identify a
published artifact, change a reader pin or extend the active catalogue's verified
selection coverage. A complete discovery catalogue and a complete availability
index are separate claims; every availability claim is bounded by its scope.

The reviewed core is `b9285872352070ae6a7be922b555098f4f3cc4d9` on
`plugin/opendata`. Its eight new observational DVNS datasets have native row
contracts but no active entries in `availability-selection.yaml`. DVNS selection
uses the indexed path, so the absence is an explicit selection error rather than
permission to infer combinations from independent catalogue dimensions.

## Scope ownership

| Scope and policy stem | Datasets | Request grid |
| --- | --- | --- |
| `dvns-cursor-observations` | `siope_inventario_enti`, `salute_posti_letto` | One unfiltered complete cursor partition each |
| `dvns-irpef-history` | `mef_irpef_dettaglio` | Native declaration `year` 2017–2025; all families and breakdowns |
| `dvns-municipal-receipts-history` | `siope_entrate_comuni` | Native `year` 2024, 2025, 2026; no territorial filter |
| `dvns-siope-payments` | `siope_asl`, `siope_province`, `siope_regioni`, `siope_citta_metropolitane` | One unfiltered complete cursor partition each |

The identifier for municipal receipts is `siope_entrate_comuni`; the conversational
name `siope_comuni_incassi` is not a source identifier. Measure labels are copied
from the core's explicit English workspace content and cover every configured
measure exactly. Unit labels cover the canonical outputs, including the explicit
cent-to-euro conversions. No source endpoint or identity is invented here.

The cursor-observation scope allows 100 pages per partition and 100,000 index
records. The historical scopes allow 100 pages per partition and two million
records. Payments require up to 4,000 pages per partition, with a two-GiB total
response budget and two million index records. These are explicit build limits,
not measured claims about complete archive sizes. A source that exceeds them must
fail visibly. Index construction streams pages; the core's separate 20,000-row
payment acquisition cap remains unchanged.

The one-day evidence lifetime follows the existing publisher authoring policy.
Replaying an old capture preserves its original observation timestamps and does
not renew that lifetime. The new scopes are not added to a scheduled update plan.

## Selection bindings

`scopes/dvns-observations.selections.json` is a `datasets` component for future
assembly with the existing strict SDG reader schema. Each contained dataset entry
validates as `DatasetSelection`. It intentionally contains no `indexes` object,
artifact revision, digest or snapshot pin. It cannot be used as a complete reader
policy or directly activated. The planned index names match their scope stems.

| Dataset | Native acquisition binding | Additional axes |
| --- | --- | --- |
| Entity census | No arguments; acquire all three native pages | `entity_type` |
| Hospital beds | No arguments; acquire all eleven native pages | `region_source`, `discipline_type`, `discipline` |
| IRPEF details | `period` → integer `year`; `family` → `family` | `family`, `breakdown`, `income_class`, `breakdown_value`, `measure_nature`, `measure_occurrence` |
| Municipal receipts | `reference_year` → integer `year` | `reference_year` |

All four also retain `territory`, `period`, `measure` and `unit`. All axes other
than `period` are single-valued, and their explicit order narrows the conditional
options before the period range. For receipts this selects one source year per
timeline. A multi-year comparison is not fabricated by treating different source
years and their disjoint periods as a Cartesian product.

Neither the entity census nor hospital beds declares a native `year` argument.
Adding one would be an invalid request. Their complete unfiltered acquisitions
already fit the source row budget, so no unqualified text-search binding is
required. For IRPEF, `breakdown` remains an exact projected selection axis;
the native request retrieves the full selected family before projecting the
confirmed observation. This is the complete `year=2021,family=bonus_irpef`
request already qualified by retained receipts. A narrower native breakdown
argument is not necessary for correctness or for that qualified request's budget.

Municipal receipts delegate territorial routing to the provider contract:
country aggregates add no argument, regional aggregates bind native region
labels, and accounting entities bind their source tax code. Do not add a competing
territory binding to deployment configuration. The publication scope varies only
`year`; a filtered municipal response also carries unfiltered national context,
which cannot truthfully be bound to the municipal or regional request argument.

Hospital periods preserve the exact day `2023-01-01`, including autonomous
provinces as distinct source territories. Census and IRPEF retain annual bounds.
Receipts retain monthly and accumulated coverage, including `2026-01/2026-09`;
September's calendar boundary does not assert a completed September. The source
year is a separate dimension. The reader offers `period_range` for these actual
calendar bounds. Tax years, schema identifiers, publication dates and extraction
dates remain provenance rather than inferred observation periods.

## Offline evidence and verification

The core's retained fixtures are `cursor-observations.json.gz`,
`municipal-receipts.json.gz` and `irpef-source-tables.json.gz` under
`server/tests/fixtures/opendata/dvns`. Their original response body digests were
verified before replay. Only JSON-RPC request IDs are rebound; structured source
content is retained. No source request, catalogue database write, upload or
activation was performed for this audit.

All four scope files resolve without inventory network access, validate with
`BuildSpec`, and pass the real DVNS `contract` validator. Their policies validate
with the publisher's `policy_from`. Every binding's axes match the projected
coordinate axes and the reader-language labels.

Offline verification traversed real native pagination and projection, inserted
the resulting coordinates using the consumer's SQLite insertion contract, then
exercised every conditional selection step through `prepare_choices`. It used the
deployment limits of 10,000 options and 8,192 cells. Final cells passed through
`indexed_cells` and `fetch_selection_cell` using exact retained native requests.
This verifies the authored bindings and source scope; it does not substitute for
building and importing a complete publication archive.

| Qualified path | Projected coordinates used | Exact acquisition pages |
| --- | ---: | ---: |
| Complete entity census | 2,814 | 3 |
| Complete hospital beds, selecting autonomous province 21 | 6,114 | 11 |
| Complete IRPEF bonus 2021, selecting source category `Mancante/errata` | 16,762, including 1,242 explicit missing cells | 10 |
| Municipal tax-code route `00008010803`, 2025 | 108 from retained response | 1 |
| Calabria aggregate route, 2025 | 1,296 from retained first regional response | 1 |
| National aggregate route, partial 2026 | 1,290 from retained first national response | 1 |

The municipal coordinate counts in this table describe the retained qualification
responses, not complete national or regional index coverage. Aggregate acquisition
is independent of the municipal cursor. The exact municipality route is exhausted.

All four payment first pages additionally validate with the authored scopes:
100 distinct coordinates each, with `management`, `compartment`, `valid_from`
and `valid_to` beyond the four base axes. These are accounting entities, not a
territorial allocation of recipients or an ISTAT municipality join.

Local macOS verification: `python3 -m unittest discover -s tests -v` passed all
94 publisher tests in 20.957 seconds, with isolated temporary directories and
loopback HTTP servers. The first sandboxed attempt could not bind loopback;
the authorized local rerun passed. JSON/model validation and whitespace review
passed. No engine code or Python module changes were made. Linux, Windows,
authenticated publication and live deployment activation were not tested here.

Local qualification script and result are retained as
`/private/tmp/sdg-verify-dvns-scopes-20260910.py` and
`/private/tmp/sdg-dvns-scope-qualification-20260910.json`; the publisher suite log
is `/private/tmp/sdg-dvns-publisher-tests-20260910.log`. Run the script with the
reviewed core's `server` and this publisher checkout on `PYTHONPATH`, using the
core Python environment. The result records scope digests, axes, arguments,
calendar bounds, coordinate counts and exact acquisition page counts.

## Remaining minimum work

1. Build the complete census/hospital index from the retained complete source
   pages and exact metadata receipts, if all required requests and their original
   freshness still qualify; otherwise perform an explicit coordinated fresh
   collection. Fourteen observation pages are already retained.
2. Collect complete IRPEF history. The nine annual metadata responses declare
   25,534 source rows in 79 files and 18 schemas. At the configured 100 rows per
   page this is 260 observation requests across the nine year partitions; nine
   first pages are retained. The complete 2021 bonus traversal alone does not
   establish complete history. Empty releases and absent source files remain
   explicit, not zero-filled observations.
3. Collect each complete national municipal-receipts year. The retained complete
   Calabria 2025 traversal is not a national traversal. Obtain each year's native
   municipality count and exhaust it consistently; do not substitute the ISTAT
   municipality census for the source's accounting-entity inventory.
4. Qualify an exact usable acquisition filter for each large payment corpus
   before starting national collection. Current native declarations are 334,479,
   270,194, 150,088 and 56,188 rows: 8,110 pages at the configured page size, with
   only four first pages retained. An unfiltered acquisition exceeds the core's
   row cap. `query` is native free text, not a demonstrated exact entity filter.
   No payment selection binding is supplied until complete native responses
   establish the filter's behavior and the exact projected observation.
5. Independently validate each complete archive, publish it with its actual
   immutable receipt, then assemble and verify a concrete reader policy with the
   corresponding authored dataset bindings. The published archive must contain
   every bound dataset and the exact axes. Register the real pin and activate only
   after these checks. Add the qualified scopes to the scheduled update plan and
   update the Hub card from validated artifact counts.

All future native reads require the shared pacing deployment authorized by the
coordinator. These authoring files neither initialize pacing nor authorize
parallel source access. Retained page counts may inform a plan but cannot prove
that independently acquired pages share a current source revision. None of these
steps requires a geographic-boundaries change: the existing native territorial
identities and the provider-owned routes remain explicit.
