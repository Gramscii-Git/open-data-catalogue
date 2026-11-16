Gramscii European Open Data Catalogue
=====================================

A catalogue of 78,150 public datasets from 34 European, international and Italian
providers: what each dataset is, how it is structured, which codes and labels it uses
in each published language, where it can be read, and under which terms. It is built
by Gramscii from the providers' own catalogues and structure services and published
here as Apache Parquet tables.

The catalogue holds metadata only. It contains no observation values, feature
geometries, rasters or granules, and no search vectors: values stay with the original
provider, which each entry names and links.

Release:        snapshot taken 2026-11-11T19:00:06Z
Bucket:         s3://gramscii-european-open-data-catalogue (eu-central-1), public,
                readable without an AWS account
Same release:   https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue
                one verified archive, SHA-256 bfeb1c787f4f1de993cf2ff98dbfe8ce4d1f41519d6f0884569e44a83d9e9c1a
Documentation:  https://github.com/Gramscii-Git/open-data-examples/tree/main/european-open-data-catalogue
Publisher:      https://github.com/Gramscii-Git/open-data-catalogue


Providers (partition ids)
-------------------------
Official statistics      istat, eurostat, eurostat-comext, ec-empl, ec-grow, oecd, ilo,
                         ecb, bis, bundesbank, insee, fao
Italian public finance   dvns (Dove vanno i nostri soldi), cruscotto (AgID's Cruscotto Italia)
National open data       datagouv (data.gouv.fr)
Italian cities           milano, roma, torino, bologna, napoli
Urban planning           milano-pgt, lombardia-pgt, torino-prgc, bolzano-puc, genova-puc,
                         veneto-ptrc, sardegna-puc, sicilia-prg
Sardinia                 datigov-sardegna (Sardinia's datasets on dati.gov.it),
                         sardegna-salute, sardegna-autonomie, sardegna-geoserver,
                         gbif-sardegna (GBIF occurrences), eea-sardegna (EEA map services)

catalogue/manifest.json counts every table's rows and names every file.


Layout
------
README.txt
catalogue/manifest.json
catalogue/<table>/provider=<id>/data_0.parquet
catalogue/opendata_native_objects/data_0.parquet

Every table keyed by provider is partitioned the Hive way, provider=<id>: a reader
that needs one provider reads only that provider's files, and DuckDB, Amazon Athena,
Apache Spark and PyArrow expose provider as a column. Files are compressed with
Zstandard.

manifest.json holds taken_at (the snapshot's time, UTC), archive (SHA-256 and size of
the verified archive these tables were written from), document_contract_sha256 (the
contract the searchable descriptions were built under), tables (rows, partition column
and every column with its type) and files (every Parquet file with its size, SHA-256
and rows). Read it first and check the files you read against it.


Tables (rows in this release)
-----------------------------
opendata_catalog            78,150     one per dataset: titles and names per language,
                                       descriptions, categories, keywords, agency, period
                                       covered, last update, links (sources), licence,
                                       attribution
opendata_structures         78,150     one per dataset: dimensions, code lists, time
                                       coverage, key order, spatial reference, source
opendata_structure_dims     93,951     one per dimension of a data structure
opendata_terms           3,949,157     one per code of a code list, per language
opendata_labels                  0     one per dataset label in one language
opendata_meta_reports        1,293     one per methodology or quality report
opendata_document_codes     85,718     one per dimension a searchable description names
opendata_documents          30,069     one per dataset's searchable description, per language
opendata_native_objects     21,556     one per provider response kept verbatim, by SHA-256
opendata_native_bindings    12,643     one per dataset read from native objects
opendata_native_exclusions 257,520     one per native reference left out, with the reason
opendata_held_codes        117,541     one per dimension of a dataset: the codes holding data

JSON columns hold nested metadata as the provider described it; read them with a JSON
function rather than expecting a fixed shape.


Reading
-------
DuckDB, no download and no AWS account:

  INSTALL httpfs; LOAD httpfs; SET s3_region = 'eu-central-1';
  SELECT provider, count(*) AS datasets
  FROM read_parquet('s3://gramscii-european-open-data-catalogue/catalogue/opendata_catalog/*/*.parquet',
                    hive_partitioning = true)
  GROUP BY provider ORDER BY datasets DESC;

One provider:

  SELECT dataset_id, title, licence, period_start, period_end
  FROM read_parquet('s3://gramscii-european-open-data-catalogue/catalogue/opendata_catalog/provider=istat/*.parquet');

AWS CLI:

  aws s3 ls --no-sign-request s3://gramscii-european-open-data-catalogue/catalogue/


Rights and attribution
----------------------
Each dataset keeps its provider's terms, recorded in opendata_catalog's licence,
attribution and sources fields; consult the original provider's terms before reusing a
dataset. Gramscii's compilation and this documentation are released under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/); those terms cover Gramscii's
contribution, not the underlying sources.

The catalogue draws on the istat_lookup.duckdb territorial lookup of onData's ISTAT MCP
Server (https://github.com/ondata/istat_mcp_server) and on the opensdmx constraint
archive (https://github.com/ondata/opensdmx), under their MIT licence.


Updates and contact
-------------------
Each verified release replaces the previous one. Questions and corrections:
amministrazione@gramscii.com
