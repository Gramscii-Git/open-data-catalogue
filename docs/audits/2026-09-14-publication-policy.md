# Publication policy: retired rows, permanent structure errors and licences

The catalogue maintainer decided three publication rules on 14 September 2026.
This audit records them with the measurements they rest on. No database row,
licence value or deployment pin was changed for it, and it authorizes no reuse of
any dataset.

## Decisions

1. **Retired catalogue rows are not published.** SDG publication contract 3
   leaves datasets `sync` retired out of the exported archive, together with the
   structures, labels and documents keyed to them. The publisher refuses an
   archive that still holds a retired row. SDG keeps the rows as history.
2. **A structure error a provider declares permanent is published with its
   answer.** An error whose stored text is exactly a provider answer one of that
   provider's `dataflow_permanent_errors` rules matches is counted as
   `permanent_structure_errors` and listed on the dataset card. Every other
   structure error still rejects a release.
3. **Licences are required for served datasets.** A dataset SDG does not serve
   is published without a licence rather than with one inferred from its source
   institution. DVNS is asked to declare the rights of EPEA; the request is
   drafted below.

The first rule supersedes, for retired rows, the release block stated at the end
of [the retired catalogue rights audit](2026-09-10-retired-licences.md): those
rows no longer reach an archive, so their missing rights no longer block a
release. That audit's findings on their rights stand unchanged.

## Catalogue measured

Read-only transactions on the publication database, 14 September 2026, between
17:05 and 17:15 Europe/Rome, while the ISTAT structure collection was running:

| Provider | Current rows | Retired rows | Retired without licence |
| --- | ---: | ---: | ---: |
| cruscotto | 25 | 0 | 0 |
| dvns | 55 | 0 | 0 |
| eurostat | 8,156 | 102 | 102 |
| ilo | 1,212 | 0 | 0 |
| istat | 4,905 | 3 | 3 |
| oecd | 1,546 | 3 | 3 |
| **total** | **15,899** | **108** | **108** |

- Served datasets without a licence: 0.
- Current datasets without a licence: 1, `dvns:istat_epea`, which is active and
  searchable but not served.
- `minimum_datasets` in `publisher.example.toml` becomes 15,899, the current
  datasets an archive under contract 3 carries.

No licence can be projected onto the retired rows from provider terms. SDG's
`providers.yaml` declares the terms of Eurostat, OECD and ILO with
`scope: dataset-specific` and those of ISTAT with
`scope: provider-with-exceptions`. The earlier audit found dataset-specific
exceptions and restrictive conditions among exactly these rows.

## Structure errors measured

The same transactions classified every stored structure error with SDG's
`declared_permanent_error` and the rules in `providers.yaml` at SDG `main`
`9c3b65cc`. No stored error belongs to a retired dataset.

**ISTAT, 8 errors, all on served datasets:**

- `123_712`: the provider's mapping-set answer, stored bare. It is declared
  permanent.
- `115_362`: the same answer, stored after the retries were exhausted,
  before the rule existed. It counts as an ordinary error until a resumed
  structure run retries it and stores the bare answer.
- `123_712_DF_DCAR_INDBILPER_1`: `no answer within 600s`, left by the
  collection's patience for a later run.
- `31_739_DF_DCCV_SPEMEFAM_7`: `500 {"errorCode":"DATAFLOW_NOT_FOUND",...}`.
  The body does not name the dataflow, so no rule may declare it permanent.
- `124_1156`, `124_1157` and their `DF_DCAR_*_UNI_1` flows:
  `SDMX dimension 'BODY' has no unique referenced concept`. SDG's parser
  refuses these answers. The cause is still to be read from the structure
  response.

**OECD, 324 errors, all written on 8 September:**

- 11 declared permanent: `DF_SDG_GLC`, `DSD_DASHBOARD@MUNI_CHANGE`,
  `DSD_GOV@DF_GOV_2025`, `DSD_NAMAIN10@DF_TABLE4_PPP_P31S14`,
  `DSD_REG_CLIM@DF_DROUGHT`, `DSD_REG_CLIM@DF_HEAT_STRESS`,
  `DSD_REG_DEMO@DF_REGION_TYPE`, `DSD_REG_ENV@DF_ENV`, `DSD_REG_TOUR@DF_TOUR`,
  `DSD_REICO_FULL@DF_ALL` and `DSD_SOE@DF_SOE_COU`.
- 295 × `429`: that run paced OECD at one call per second, above its published
  limit. SDG PR 165 paces it at 4 seconds.
- 10 × `404 Could not find requested structures` and 8 × `500 Value cannot be
  null. (Parameter 'maintainableReference')`. These are measured again after
  the OECD run at the new pace. A rule must name its dataflow in the body; these
  bodies do not, so they stay release defects.

The database therefore cannot yet be released. The ISTAT collection and an
OECD structure run come first.

## Request to DVNS

The catalogue maintainer sends this as an issue on
[DoveVannoINostriSoldi](https://github.com/Italian-Builders-Org/DoveVannoINostriSoldi),
in the project's language. The evidence is in SDG's
`docs/audits/2026-09-14-dvns-rights.md`.

> **Titolo:** Dichiarare la licenza della serie Istat EPEA 2016–2022 nel catalogo MCP
>
> Nel catalogo esposto dal server MCP, la sorgente della serie `istat_epea`
> (Istat `IT1,97_953,1.0`, anni 2016–2022, edizione `2025M2`) non porta né
> `license` né `licenseUrl`. La specifica
> `scripts/etl/specs/istat-epea-2016-2022.source.json` dichiara
> `licenseId: not-declared`.
>
> Istat pubblica questa edizione
> ([Spesa per la protezione dell'ambiente, anni 2016–2022](https://www.istat.it/sistema-informativo-6/spesa-per-la-protezione-dellambiente-anni-2016-2022/))
> e dichiara la licenza dei dati diffusi sul sito e nelle banche dati nella pagina
> [Open data](https://www.istat.it/dati/open-data/), con le condizioni delle
> [note legali](https://www.istat.it/note-legali/).
>
> Potete verificare i diritti di questa serie, dichiararli nella specifica con la
> fonte e propagarli in `license` e `licenseUrl` della risposta del catalogo? Un
> catalogo a valle può così riportarli senza dedurli da solo. Da parte nostra non
> li deduciamo: finché la risposta non li dichiara, la serie resta pubblicata
> senza licenza e non viene servita.

If DVNS declares the rights, a normal `sync` records them. If EPEA becomes a
served dataset, its licence becomes a release requirement.

## Order

SDG contract 3 lands before a publisher that requires it is deployed. The
running ISTAT collection keeps its pinned harvester and publisher revisions. No
file the document contract hashes changes, so stored documents stay current.
