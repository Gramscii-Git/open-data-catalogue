# Retired catalogue rights audit

The strict publication gate remains blocked by missing historical rights
metadata. No database row, licence value, quality limit or deployment pin was
changed for this audit. This report does not authorize reuse of the affected
datasets.

## Evidence and root cause

The isolated publication database contained 1,721 retired rows without licences:
1,616 ISTAT, 102 Eurostat and three OECD. All 1,721 corresponding rows already
had `licence: null`, empty `sources` and null `attribution` in the previously
published discovery archive at revision
`8854722f8a035cbed57b1cb2bbbed4a297f5c188`. The last reconciliation did not erase
these fields.

Migration `0004_catalog_provenance.sql` added nullable licence and attribution
columns on August 31 in core commit `f68a5600`. SDMX `source_fields` was added on
September 1 in `ab980cf3`; the withdrawn rows never received its fields through a
subsequent successful native catalogue/enrichment pass. The stored ISTAT registry
timestamps range from July 30 to August 24. The original archive had 1,613 of
these ISTAT rows active; the other three ISTAT, 102 Eurostat and three OECD rows
were inactive but not yet marked retired.

The current complete Hub inventory reconciliation marks absent ISTAT rows
retired. That flag alone does not establish that the same identifier is absent
from the separate native SDMX registry. Existing `enrich_registry` reads that
registry independently, writes its source fields and marks returned rows active
again. The two inventory roles must be reconciled explicitly; historical rows
must not oscillate between retirement and activation solely because the last
operation used a different catalogue surface.

## ISTAT: distinguish registry identity, queryability and rights

| Stored reference class | Retired rows |
| --- | ---: |
| Numeric base identifiers with a non-virtual DSD | 528 |
| Other identifiers with a non-virtual DSD | 800 |
| `MDM:VIRTUALDSD(1.0)` | 288 |

All 1,616 rows have agency `IT1` and a recorded registry observation timestamp.
The repository's retained registry excerpt contains six of the numeric base
identifiers, including `101_1015`. That entry has a real
`IT1:DCSP_COLTIVAZIONI(1.1)` structure reference and shares its native
`DDBDataflow` annotation with a displayed child flow. It cannot be classified
as an invented or non-queryable identity merely because the Hub omits it.

The retained untitled-registry excerpt contains two more affected identifiers,
including `DF_BULK_CEN2011_DICA_N02MCOM`. It explicitly declares `ONLY_FILE`, a
native attachment URL and `MDM:VIRTUALDSD(1.0)`. These are not ordinary SDMX data
queries. A missing queryable DSD is not proof that the attached source artifact
was withdrawn. The current configured non-queryable reference correctly prevents
issuing an SDMX observation query for that virtual structure.

The stored report keys match 549 ISTAT reference-report records: 540 retain text,
nine retain permanent source errors. None of those report texts contains an
explicit copyright, licence or Creative Commons declaration. The registry
excerpts preserve identities and metadata references, but do not supply a
dataset-specific rights statement.

ISTAT's [open-data page](https://www.istat.it/dati/open-data/) states its
licensing policy for published data. Its
[legal notice](https://www.istat.it/note-legali/) retains exceptions and
third-party rights. Those current pages are verified HTTP 200 evidence of the
provider policy, not evidence that every historical row has been checked for
exceptions. No blanket backfill is justified by this audit.

The [official SDMX service notice](https://www.istat.it/classificazioni-e-strumenti/web-services-sdmx/)
declares an IP-wide limit of five queries per minute and a possible one-to-two-day
block after excess traffic. No new request was sent to `esploradati.istat.it` by
this audit. Existing connection failures are not sufficient to diagnose an IP
block, nor to infer withdrawal or missing rights for any dataset.

## Eurostat: actual historical withdrawal and distribution-level rights

Exactly 98 affected rows refer to `med_esms`; the other four are saved views of
`HLTH_SILC_08` or `HLTH_SILC_10`, containing `$DV_` in their identifiers. Their two
stored reference reports retain text but no explicit licence declaration; one
also records a later HTTP 404.

The official [data.europa.eu record for MED_AG1](https://data.europa.eu/api/hub/search/datasets/l5qkqxv7fakd17p35b7mtq)
was fetched successfully and explicitly identifies `med_ag1`, Eurostat as
publisher, its DOI and discontinuation on July 31, 2026. This is an exact
identifier match, not a title-based guess. Its current CC BY 4.0 declaration is
attached to a single distribution of the **catalogue TOC XML**. It must not be
transferred to the removed observation distribution.

The [historical MED reference metadata](https://ec.europa.eu/eurostat/cache/metadata/en/med_esms.htm)
describes ENP-South data supplied by national authorities. The web retrieval
retains that page, while the direct HTTP capture in this audit returned 404; the
cached text is not a successful current-source receipt. The
[Eurostat reuse notice](https://ec.europa.eu/eurostat/help/copyright-notice),
captured as HTTP 200, includes dataset-specific and third-party exceptions and
commercial-use restrictions for specified country data. Recording a general
unconditional open-data grant would therefore be inaccurate.

The verified data.europa.eu retrieval provides a practical way to recover
historical identifiers, withdrawal dates, provenance and **scoped distribution
licences**. Every candidate distribution must still match the exact dataset and
artifact being licensed. A licence attached to a replacement catalogue link
cannot satisfy the missing observation-rights record.

## OECD: three distinct cases

- `OECD.EDU.IMEP:DSD_EAG_SAL_STA@DF_TCH_COM(2.0)` is the teachers' comparative
  salary dataset. Its exact native dataflow request returned HTTP 404 with
  `No Results Found`. A cached official Data Explorer page still describes it;
  that does not establish current registry availability or recover its rights
  metadata.
- `OECD.FATF:DSD_RAT@DF_TC_DD_PUBLIC(1.0)` and
  `OECD.FATF:DSD_RAT_5@DF_TC_DD_5_PUBLIC(1.0)` both retain explicit
  confidentiality and non-disclosure conditions in their original stored
  descriptions. Their public-looking identifiers do not override that text.

The [OECD terms](https://www.oecd.org/en/about/terms-conditions.html) and
[FATF terms](https://www.fatf-gafi.org/en/pages/terms-conditions.html) both require
attention to dataset-specific restrictions and third-party ownership. A general
permission cannot erase the conditions already recorded for the FATF entries.
Further direct metadata captures returned HTTP 403 with error code 1010; direct
terms-page captures also returned 403. The web tool could read the terms pages,
but no successful current native rights receipt for the three datasets was
obtained. No additional attempts or access-control circumvention followed.

## Permitted next operations and actual blockers

1. Preserve the original catalogue archive and the exact null values as evidence.
   Compare identifiers, agencies, versions and structure references; do not join
   by similar titles or infer replacement datasets from prefixes.
2. When the native ISTAT registry is reachable, perform one paced complete
   metadata acquisition, retaining original bytes and an HTTP receipt. Reconcile
   registry existence separately from Hub visibility and SDMX queryability.
   Use the existing native enrichment boundary for verified returned metadata;
   do not bulk-update every retired row by provider name.
3. For each rights repair, retain the exact dataset/version evidence and the
   applicable rights statement, its scope, source URL, digest and capture time.
   Preserve restrictive terms and exception findings. Missing evidence is an
   unresolved row, not an instruction to invent a licence label.
4. For Eurostat historical entries, inspect official DCAT distributions and
   historical reference metadata. Record the proven MED_AG1 withdrawal and
   catalogue-distribution rights without presenting them as observation rights.
   Verify saved-view relationships natively before transferring any metadata.
5. For the two FATF records, preserve the explicit restrictive text. An
   authoritative clarification or an applicable dataset-specific rights notice
   is required before claiming a grant of reuse. Public access alone is not
   such a grant. The missing teachers' native metadata is a separate problem.
6. Apply only reviewed, evidence-backed field changes in a transaction that
   checks the expected old row. Keep lifecycle flags and unrelated fields out
   of a rights-only repair. Export again and run the unchanged strict policy.

The current evidence is insufficient to approve all 1,721 historical licence
repairs. The full discovery release remains blocked until these rows have
verifiable applicable rights metadata. No policy exception, row deletion,
placeholder licence or metadata-to-observation rights substitution was made.

## Reproduction artifacts

Local audit directory: `/private/tmp/opendata-retired-licences-20260910`.
`audit.py` executes a read-only database transaction and compares the original
archive; `summary.json`, `retired-catalogue.json`,
`retired-original-catalogue.json` and `retired-meta-reports.json` preserve the
measurements. `source-cases.json` and `capture.py` describe the bounded public
requests. `sources/receipts.jsonl` records original bytes, status, timestamps,
sizes, hashes and final URLs, including failed responses. These runtime artifacts
are deliberately outside version control.

The native registry excerpt hashes are
`82bd38666487531e9c3874443eb5d9fda6efe1ae8175d3ab5adefebc632090b2`
and `c7a1a9ccc89c3000c5cac7e90dd06b6f76c9f5f0f3e6649d7e52cc4c369ef6cd`.
They identify the already retained core fixtures
`istat_registry_excerpt.xml` and `istat_registry_untitled_excerpt.xml`.
