"""The S3 export writes a verified archive's tables as Parquet through the DuckDB command line."""

import base64
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_release import write_archive

from catalogue.s3_export import copy_statement, export, load_tables, sha256_file

ROOT = Path(__file__).resolve().parents[1]
DUCKDB = shutil.which("duckdb")
VALUES = {
    "VARCHAR": "text", "BOOLEAN": True, "BIGINT": 7, "DATE": "2026-10-01", "TIMESTAMP WITH TIME ZONE": "2026-10-17T08:10:12+02:00",
    "JSON": {"nested": [1, "two"]}, "VARCHAR[]": ["A", "B"], "BLOB": base64.b64encode(b"\x00native").decode(),
}


def table_rows(tables):
    """Two rows a table for every declared column, the partitioned ones under two providers."""
    result = {}
    for name, table in tables.items():
        result[name] = []
        for index, provider in enumerate(("istat", "veneto-ptrc")):
            row = {column: VALUES[kind] for column, kind in table["columns"].items()}
            for column, kind in table["columns"].items():
                if kind == "VARCHAR":
                    row[column] = f"{column}-{index}"
            if "provider" in row:
                row["provider"] = provider
            result[name].append(row)
    return result


@unittest.skipIf(DUCKDB is None, "the DuckDB command line is not installed: the S3 export is unverified here")
class S3Export(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.tables = load_tables(ROOT / "s3-tables.json")
        self.rows = table_rows(self.tables)

    def archive(self, rows, declared=None):
        path = self.directory / "open-data-catalogue.tar.gz"
        write_archive(path, rows, declared)
        return path, sha256_file(path)

    def query(self, sql):
        return json.loads(subprocess.run([DUCKDB, "-json", "-c", sql], check=True, capture_output=True, text=True).stdout)

    def test_duckdb_reads_a_staged_file_with_one_thread_under_the_given_memory_limit(self):
        table = self.tables["opendata_structures"]
        statement = copy_statement(table, self.directory / "rows.jsonl.gz", self.directory / "data_0.parquet",
                                   memory_limit="2GB", longest_row=4096)
        self.assertTrue(statement.startswith("SET memory_limit='2GB'; SET threads=1; SET preserve_insertion_order=false; "
                                             "COPY "))
        self.assertIn(f"read_json('{self.directory / 'rows.jsonl.gz'}', ", statement)
        self.assertIn("maximum_object_size=4096,", statement)
        self.assertNotIn("/dev/stdin", statement)
        self.assertNotIn("PARTITION_BY", statement)

    def test_a_memory_limit_that_is_not_a_size_is_refused(self):
        with self.assertRaises(ValueError):
            copy_statement(self.tables["opendata_structures"], self.directory / "rows.jsonl.gz",
                           self.directory / "data_0.parquet", memory_limit="2GB'; SELECT 1; '", longest_row=4096)

    def test_a_provider_whose_rows_arrive_again_after_another_leaves_nothing(self):
        rows = copy.deepcopy(self.rows)
        rows["opendata_terms"].append({**rows["opendata_terms"][0]})
        rows["opendata_terms"][-1]["language"] = "later"
        archive, digest = self.archive(rows, {name: len(held) for name, held in rows.items()})
        output = self.directory / "catalogue"
        with self.assertRaisesRegex(ValueError, "opendata_terms: rows of provider 'istat' arrive after another"):
            export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertFalse(output.exists())

    def test_a_provider_a_path_cannot_hold_leaves_nothing(self):
        rows = copy.deepcopy(self.rows)
        for row in rows["opendata_catalog"]:
            row["provider"] = "../istat"
        archive, digest = self.archive(rows)
        output = self.directory / "catalogue"
        with self.assertRaisesRegex(ValueError, "opendata_catalog: row 1 names no provider a path can hold"):
            export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertFalse(output.exists())

    def test_a_partitioned_table_without_rows_writes_no_file(self):
        rows = {**copy.deepcopy(self.rows), "opendata_labels": []}
        archive, digest = self.archive(rows, {name: len(held) for name, held in rows.items()})
        output = self.directory / "catalogue"
        result = export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertEqual(result["tables"]["opendata_labels"]["rows"], 0)
        self.assertFalse([path for path in result["files"] if path.startswith("opendata_labels/")])

    def test_a_row_longer_than_declared_leaves_nothing_and_names_its_size(self):
        archive, digest = self.archive(self.rows)
        output = self.directory / "catalogue"
        with self.assertRaisesRegex(ValueError, "past the longest row declared"):
            export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=16)
        self.assertFalse(output.exists())

    def test_every_table_is_written_partitioned_and_named_in_the_manifest(self):
        archive, digest = self.archive(self.rows)
        output = self.directory / "catalogue"
        result = export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertEqual(json.loads((output / "manifest.json").read_text()), result)
        self.assertEqual({name: table["rows"] for name, table in result["tables"].items()},
                         {name: 2 for name in self.tables})
        self.assertIn("opendata_catalog/provider=veneto-ptrc/data_0.parquet", result["files"])
        self.assertIn("opendata_native_objects/data_0.parquet", result["files"])
        for path, receipt in result["files"].items():
            self.assertEqual(receipt["sha256"], hashlib.sha256((output / path).read_bytes()).hexdigest())
        self.assertEqual(result["files"]["opendata_catalog/provider=istat/data_0.parquet"]["rows"], 1)
        self.assertEqual(result["files"]["opendata_native_objects/data_0.parquet"]["rows"], 2)
        self.assertEqual(result["document_contract"], json.loads((ROOT / "tests/fixtures/document-contract.json").read_text()))
        catalogue = self.query(f"SELECT provider, dataset_id, names, synced_at FROM read_parquet("
                               f"'{output}/opendata_catalog/*/*.parquet', hive_partitioning=true) ORDER BY provider")
        self.assertEqual([row["provider"] for row in catalogue], ["istat", "veneto-ptrc"])
        self.assertEqual(catalogue[0]["names"], {"nested": [1, "two"]})
        native = self.query(f"SELECT decode(body) AS body, octet_length(body) AS size FROM "
                            f"'{output}/opendata_native_objects/data_0.parquet' LIMIT 1")[0]
        self.assertEqual(native["size"], len(b"\x00native"))
        codes = self.query(f"SELECT codes FROM read_parquet('{output}/opendata_held_codes/*/*.parquet') LIMIT 1")[0]
        self.assertEqual(codes["codes"], ["A", "B"])

    def test_a_row_outside_the_declared_columns_leaves_nothing(self):
        rows = copy.deepcopy(self.rows)
        rows["opendata_terms"][1]["unexpected"] = "value"
        archive, digest = self.archive(rows)
        output = self.directory / "catalogue"
        with self.assertRaisesRegex(ValueError, "opendata_terms: row 2 does not hold exactly the declared columns"):
            export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertFalse(output.exists())

    def test_only_the_verified_archive_is_exported(self):
        archive, _ = self.archive(self.rows)
        with self.assertRaisesRegex(ValueError, "does not match the verified SHA-256"):
            export(archive, "0" * 64, self.tables, [DUCKDB], self.directory / "catalogue", memory_limit="1GB", longest_row=2**20)

    def test_rows_must_match_the_archive_manifest(self):
        declared = {name: 2 for name in self.tables} | {"opendata_documents": 3}
        archive, digest = self.archive(self.rows, declared)
        output = self.directory / "catalogue"
        with self.assertRaisesRegex(ValueError, "opendata_documents: rows or bytes differ from the archive manifest"):
            export(archive, digest, self.tables, [DUCKDB], output, memory_limit="1GB", longest_row=2**20)
        self.assertFalse(output.exists())

    def test_a_value_duckdb_cannot_read_as_declared_is_refused(self):
        rows = copy.deepcopy(self.rows)
        rows["opendata_structures"][0]["obs_count"] = "many"
        archive, digest = self.archive(rows)
        with self.assertRaisesRegex(RuntimeError, "opendata_structures: DuckDB did not write the table"):
            export(archive, digest, self.tables, [DUCKDB], self.directory / "catalogue", memory_limit="1GB", longest_row=2**20)


class S3Tables(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "s3-tables.json"
        self.spec = json.loads((ROOT / "s3-tables.json").read_text())

    def refused(self, message):
        self.path.write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError, message):
            load_tables(self.path)

    def test_the_declaration_covers_exactly_the_archive_tables(self):
        del self.spec["tables"]["opendata_labels"]
        self.refused("exactly the archive tables")

    def test_a_column_needs_a_declared_type(self):
        self.spec["tables"]["opendata_terms"]["columns"]["name"] = "TEXT"
        self.refused("every column needs one of")

    def test_a_partition_is_a_text_key_column(self):
        self.spec["tables"]["opendata_terms"]["partition"] = "name"
        self.refused("a partition must be a text column of the table key")

    def test_the_table_key_is_declared(self):
        del self.spec["tables"]["opendata_terms"]["columns"]["code"]
        self.refused("declared columns lack the table key")


if __name__ == "__main__":
    unittest.main()
