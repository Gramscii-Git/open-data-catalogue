# Verified combined municipal catalogue

The schema-4 discovery release contains 23,612 catalogue
entries, 22,465 searchable entries and 27,043 language-specific documents from
eleven providers. Titles, descriptions, identifiers, original languages, licences, modification
dates, structures and native evidence retain their source provenance. Catalogue metadata,
individual distributions and acquired observations have distinct counts and contracts.

## Immutable release

- [Combined archive](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue/resolve/80cf77126adef9eae78dfccb73adbfa09cdaa122/open-data-catalogue.tar.gz): 9,596,005,562 bytes, SHA-256
  `a825f403f0d580e60d6b961f39a793e15f9976978ec06926a1924aba435415a9`.
- Archive revision: `80cf77126adef9eae78dfccb73adbfa09cdaa122`. Every changed release file is downloaded from
  that immutable commit and checked against its measured local size and SHA-256.
- [Release card](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue/blob/7a57c136db4b80f66ae21915184583bd2b14ab04/README.md)
  and [readback receipt](https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue/resolve/7a57c136db4b80f66ae21915184583bd2b14ab04/catalogue-publication.json).
- Tested SDG runtime implementation: `85381f09b6657caa83c0036c7a12e7bc688e6645`.
  Snapshot export implementation: `9fa898350b0d909da69fb09b2f2afbd2e7855007`. Only retrieval identity recognition
  and its tests change between these commits; all snapshot and document contracts are identical.
  Publisher library base:
  `7f3ebcb095fe0ded0d84cd7eb4052fd3d9ce9f5a`.
- Document contract: `58718f0ef6d70ac60184b8e37f96fe5303fdceca9a29647031175371c659863e`.

## Measured archive membership

| Provider | Catalogue entries | Searchable entries |
| --- | ---: | ---: |
| bologna | 357 | 357 |
| cruscotto | 25 | 25 |
| dvns | 54 | 54 |
| eurostat | 8,138 | 7,592 |
| ilo | 1,211 | 996 |
| istat | 4,526 | 4,525 |
| milano | 3,289 | 2,904 |
| napoli | 320 | 320 |
| oecd | 1,514 | 1,514 |
| roma | 3,066 | 3,066 |
| torino | 1,112 | 1,112 |

The archive has 10,069 explicit portable exclusions.
Complete metadata rows outside current search membership do not establish acquisition
availability. Search requires a verified structure, supported reader and current document.

The municipal source inventories contain Napoli 37 datasets/323 distributions, Roma
365/7,203, Torino 2,118/3,389 plus one dataset without a distribution, and Bologna 705
datasets with 8,541 alternative exports and 17 attachments. Qualified municipal catalogue
entries are 320, 3,066, 1,112 and 357 respectively; the four sources retain 6,766 exclusions.
Bologna contributes one selected export per native dataset; its formats are not independent
datasets. Milano's refreshed inventory contains 2,605 datasets and 5,969 distributions.

## Acquisition and residual limits

Napoli, Roma and Milano use verified CKAN DataStore schemas and query acquisition. Roma
includes 169 verified empty tables. Of the 4,855 newly qualified municipal resources,
4,686 return at least one observed record during verification. Search admission currently
requires a verified schema and working acquisition path, not a positive record count;
the 169 empty Roma tables remain searchable but supply no observations for analysis.
The archive's 1,147 metadata-only entries remain outside chat search altogether.

Torino uses official federated municipal metadata from
dati.gov.it and complete CSV downloads from the municipal resource host; its AperTO portal
returns 403 and further calls remain suspended. The national catalogue is not added as a
whole-national acquisition provider.

Bologna exposes an OpenDataSoft API, but this adapter acquires complete JSON exports.
The Torino/Bologna static contracts do not implement remote filtering. They admit at most
1,000 rows per complete response; Torino also requires UTF-8/BOM and at most 8 MiB. Larger,
unsupported, malformed or inaccessible resources remain explicitly excluded. Field names
do not establish time, territorial or cross-field availability dimensions.

The final policy excludes 215 ILO and six OECD entries from search because both their
required native domain and constraint are absent. No new ISTAT or Eurostat collection occurs.
Historical availability indexes keep their existing evidence dates and independent contracts.
This discovery release does not refresh those indexes or acquire every source's observations.

## Verification

- macOS ARM64: publisher standard-library suite, 191 tests passed with Python 3.14.6 on
  the final eleven-provider quality baseline (42.711 seconds).
  The earlier sandbox/SDG-venv attempt is retained as a failed environment diagnostic;
  independent Python and permission for local test HTTP listeners resolve it. Linux and
  Windows are not qualified by this run.
- SDG focused snapshot, selection, catalogue and municipal tests: 39 passed; affected
  Python lint and whitespace checks pass. Existing municipal acquisition and driver gates
  remain applicable to their unchanged implementation.
- SDG identity selection, catalogue filters and real tool/API tests: 60 passed. Ordinary
  municipal slugs inside prose do not override semantic questions about another provider;
  explicit references retain provider scope and acquisition qualification.
- Independent archive inspection passes the strict eleven-provider quality policy with
  zero missing required documents, licences or structures. Schema and policy checks remain
  mandatory. Large native evidence uses compressed temporary storage while retaining exact
  uncompressed member checksums and byte counts.
- Strict import into a new migrated PostgreSQL database matches all ten exported table
  counts and validates native evidence and exact document membership. Direct selection,
  licence preservation and exclusion checks cover all eleven providers in both query routes.
- The isolated production embedding/reranking check covers 20 native-title and two native-summary
  queries through Italian/English routes and four Italian municipal paraphrases with provider
  scope and globally. It is not a broad semantic
  benchmark or a recalibration of the existing ISTAT-derived relevance threshold. RAG vectors
  are derived locally and are not part of the snapshot archive.
- All 26 provider-scoped probes pass; the original 30-probe study finds 29 expected targets.
  The global question `Quanti visitatori ha avuto il Castel Nuovo di Napoli nel 2018?` misses
  the Napoli resource because its first-ranked title passage scores about -3.036, below the
  unchanged -2.635 floor. Diagnostic controls find it first globally by its native title and by
  the original question without `di Napoli`. The failed probe remains explicit; no automatic
  alternate question, threshold waiver or source-qualification exception is introduced.
- Short ISTAT probes `Morti` and `Deaths` return other mortality datasets but omit the selected
  flow. This measured recall limit is preserved in the published search evidence; source-summary
  queries are checked separately. Plain titles are not exact-identity lookups in this discovery
  contract, and the configured relevance threshold remains unchanged.
- Real production acquisitions retain verified results for Napoli (12 rows), Roma (428),
  Torino (8), Bologna (8) and refreshed Milano (288), including receipts and export checks.
- Every changed Hugging Face file passes immutable size/SHA-256 readback; the documentation
  follow-up also checks that the archive identity is unchanged.
  The official publisher evidence consumer accepts the archive and wrapped quality report.

## Repository and runtime coordination

The [Boundaries documentation change](https://github.com/Gramscii-Git/Boundaries/pull/3)
clarifies municipal qualification. All 12 existing boundary manifest digests and shape counts
pass, including the five municipal shape identities. This does not qualify any municipal
dataset-to-boundary join or add geometry; such a join needs actual identifiers, classification,
vintage and licence checks.

The source and owned integration databases remain retained until coordinated runtime cutover.
The clean import database is backed up and its exact owned copy removed after verification.
Publishing the Hub archive does not activate it in chat. The runtime session must adopt the
tested code and immutable snapshot pin, build its derived index and verify its running release.

The [machine-readable release receipt](2026-09-26-combined-municipal-release.json) records
counts, licences, languages, tested identities and immutable publication files.
