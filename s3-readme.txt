Gramscii European Open Data Catalogue
=====================================

A catalogue of $datasets public datasets from $providers European, international and Italian
providers: what each dataset is, how it is structured, which codes and labels it uses
in each published language, where it can be read, and under which terms. It is built
by Gramscii from the providers' own catalogues and structure services and published
here as Apache Parquet tables.

The catalogue holds metadata only. It contains no observation values, feature
geometries, rasters or granules: values stay with the original provider, which each
entry names and links. Its searchable descriptions are cut into passages, each with a
vector of $dimensions float32 values made by the embedder manifest.json pins.

Release:        snapshot taken $taken_at
Bucket:         s3://gramscii-european-open-data-catalogue (eu-central-1), public,
                readable without an AWS account
Same release:   https://huggingface.co/datasets/Gramscii-IT/european-open-data-catalogue
                one verified archive, SHA-256 $archive_sha256
Documentation:  https://github.com/Gramscii-Git/open-data-examples/tree/main/european-open-data-catalogue
Publisher:      https://github.com/Gramscii-Git/open-data-catalogue


Providers (partition ids)
-------------------------
$provider_groups

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
and every column with its type), passages (the embedder the vectors come from: the
SHA-256 of each of its files and the dimensions of its space) and files (every Parquet
file with its size, SHA-256 and rows). Read it first and check the files you read
against it; lay the passages' vectors only beside vectors of the same embedder.


Tables (rows in this release)
-----------------------------
$tables

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
