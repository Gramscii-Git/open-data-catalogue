"""Release contracts exercised with real archives, files and HTTP."""

import copy
import hashlib
import http.server
import io
import json
import plistlib
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path

from catalogue.archive import TABLE_KEYS, QualityError, inspect_archive
from catalogue.cli import publication_lock, schedule
from catalogue.config import load
from catalogue.discovery import dataset_readme
from catalogue.documents import digest
from catalogue.publish import file_url, revision_from_result, verify_download

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_CONTRACT = json.loads((ROOT / "tests/fixtures/document-contract.json").read_text())


def rows():
    result = {table: [] for table in TABLE_KEYS}
    result["opendata_catalog"] = [
        {
            "provider": "sample",
            "dataset_id": "a",
            "title": "Population",
            "names": {"en": "Population"},
            "active": True,
            "served": True,
            "searchable": True,
            "licence": "source terms",
        }
    ]
    result["opendata_structures"] = [
        {
            "provider": "sample",
            "dataset_id": "a",
            "harvested_at": "2026-01-01T00:00:00Z",
            "error": None,
        }
    ]
    result["opendata_documents"] = [
        {
            "provider": "sample",
            "dataset_id": "a",
            "language": "en",
            "text": "Title\nPopulation\n\nSummary\nPopulation by territory.",
        }
    ]
    result["opendata_terms"] = [
        {
            "provider": "sample",
            "language": "en",
            "scope": "codelist:AREA",
            "code": "A",
            "name": "Area A",
        }
    ]
    result["opendata_structure_dims"] = [
        {
            "provider": "sample",
            "structure_id": "S",
            "dimension_id": "D",
            "concept_scope": "codelist:AREA",
            "codelist_scope": "codelist:AREA",
        }
    ]
    document = result["opendata_documents"][0]
    document["text_hash"] = hashlib.sha256(document["text"].encode()).hexdigest()
    row = result["opendata_catalog"][0]
    document["projection"] = {
        "contract_sha256": digest(DOCUMENT_CONTRACT), "authority": "native_metadata", "source_language": "en",
        "source_sha256": digest({"title": row["title"], "metadata": {
            field: row.get(field) for field in (
                "names", "descriptions", "category_paths", "keywords", "caveat",
                "filters", "sources", "period_start", "period_end", "freshness",
            )
        }}),
        "text_sha256": document["text_hash"],
    }
    return result


def write_archive(path, tables, declared=None, *, contract=DOCUMENT_CONTRACT):
    manifest = {
        "schema_version": 2,
        "taken_at": "2026-01-01T00:00:00Z",
        "tables": {name: len(body) for name, body in tables.items()}
        if declared is None
        else declared,
        "document_contract": contract,
        "document_contract_sha256": digest(contract),
        "document_membership": {"documents": len(tables["opendata_documents"]), "missing": 0, "undeclared": 0, "contract_sha256": digest(contract)},
    }
    with tarfile.open(path, "w:gz") as archive:
        payloads = {
            f"{name}.jsonl": "".join(json.dumps(row) + "\n" for row in body).encode()
            for name, body in tables.items()
        }
        payloads["manifest.json"] = json.dumps(manifest).encode()
        for name, data in payloads.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


class Releases(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / "snapshot.tar.gz"
        self.config = load(ROOT / "publisher.example.toml")
        self.policy = copy.deepcopy(self.config["quality"])
        self.policy["minimum_datasets"] = 1
        self.policy["providers"] = {"sample": {"languages": ["en"], "vocabulary": True}}
        self.contract = copy.deepcopy(DOCUMENT_CONTRACT)
        self.policy["document_contract_sha256"] = digest(self.contract)

    def inspect(self, data):
        write_archive(self.archive, data, contract=self.contract)
        return inspect_archive(self.archive, self.policy)

    def test_valid_release_has_verified_counts_and_digest(self):
        result = self.inspect(rows())
        self.assertEqual(result["issues"], [])
        self.assertEqual(
            result["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest()
        )
        self.assertEqual(result["bytes"], self.archive.stat().st_size)
        self.assertEqual(result["tables"]["opendata_catalog"], 1)

    def test_native_english_documents_cover_declared_italian_queries_without_translation(self):
        report = self.inspect(rows())
        self.assertEqual(report["manifest"]["document_contract"]["searches"]["it"], ["en"])
        self.assertEqual(report["metrics"]["missing_documents"], 0)
        self.assertEqual(report["metrics"]["undeclared_documents"], 0)

    def test_undeclared_italian_copy_is_refused_even_when_it_has_a_valid_text_hash(self):
        data = rows()
        data["opendata_documents"].append({**data["opendata_documents"][0], "language": "it"})
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["undeclared_documents"], 1)

    def test_projection_requires_actual_native_title_and_current_source_metadata(self):
        for change in ({"names": {}}, {"period_start": "2025"}):
            with self.subTest(change=change):
                data = rows()
                data["opendata_catalog"][0].update(change)
                with self.assertRaises(QualityError) as caught:
                    self.inspect(data)
                self.assertEqual(caught.exception.report["metrics"]["invalid_document_projections"], 1)

    def test_old_projection_is_not_invented_from_matching_text_hash(self):
        data = rows()
        del data["opendata_documents"][0]["projection"]
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["invalid_document_projections"], 1)

    def test_retired_catalogue_records_are_preserved_without_current_documents(self):
        data = rows()
        data["opendata_catalog"][0]["active"] = False
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["undeclared_documents"], 1)
        data["opendata_documents"] = []
        self.assertEqual(self.inspect(data)["tables"]["opendata_catalog"], 1)

    def test_contract_pin_and_zero_missing_requirement_cannot_be_skipped(self):
        self.policy["document_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "contract digest"):
            self.inspect(rows())
        self.policy["document_contract_sha256"] = digest(self.contract)
        self.policy["maximum_missing_documents"] = 1
        with self.assertRaisesRegex(ValueError, "maximum_missing_documents=0"):
            self.inspect(rows())

    def test_partial_harvest_and_missing_licence_are_rejected(self):
        data = rows()
        data["opendata_structures"][0]["error"] = ""
        data["opendata_catalog"][0]["licence"] = None
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["structure_errors"], 1)
        self.assertEqual(caught.exception.report["metrics"]["missing_licences"], 1)

    def test_missing_structure_and_language_are_rejected(self):
        data = rows()
        data["opendata_structures"] = []
        self.policy["providers"]["sample"]["languages"].append("it")
        self.contract["providers"]["sample"]["it"] = "native_metadata"
        self.contract["searches"] = {"it": ["it", "en"], "en": ["en", "it"]}
        self.policy["document_contract_sha256"] = digest(self.contract)
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["missing_structures"], 1)
        self.assertEqual(caught.exception.report["metrics"]["missing_documents"], 1)

    def test_legacy_scopes_and_missing_dimension_mappings_are_rejected(self):
        data = rows()
        data["opendata_terms"][0]["scope"] = "AREA"
        data["opendata_structure_dims"] = []
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertEqual(caught.exception.report["metrics"]["unscoped_terms"], 1)
        self.assertTrue(
            any("lacks" in issue for issue in caught.exception.report["issues"])
        )

    def test_orphan_document_and_unknown_vocabulary_reference_are_rejected(self):
        data = rows()
        data["opendata_documents"][0]["dataset_id"] = "unknown"
        data["opendata_structure_dims"][0]["concept_scope"] = "conceptscheme:MISSING"
        with self.assertRaises(QualityError) as caught:
            self.inspect(data)
        self.assertTrue(
            any(
                "no catalogue row" in issue
                for issue in caught.exception.report["issues"]
            )
        )
        self.assertTrue(
            any("no terms" in issue for issue in caught.exception.report["issues"])
        )

    def test_duplicate_rows_and_unknown_providers_are_rejected(self):
        data = rows()
        data["opendata_terms"].append(dict(data["opendata_terms"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            self.inspect(data)
        data = rows()
        data["opendata_catalog"][0]["provider"] = "unknown"
        with self.assertRaisesRegex(ValueError, "no release policy"):
            self.inspect(data)

    def test_table_set_and_manifest_counts_are_not_advisory(self):
        data = rows()
        del data["opendata_labels"]
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.inspect(data)
        data = rows()
        declared = {name: len(body) for name, body in data.items()}
        declared["opendata_terms"] += 1
        write_archive(self.archive, data, declared)
        with self.assertRaisesRegex(ValueError, "does not match"):
            inspect_archive(self.archive, self.policy)

    def test_policy_exceptions_are_explicit_and_retained_in_the_report(self):
        data = rows()
        data["opendata_catalog"][0]["licence"] = None
        self.policy["maximum_missing_licences"] = 1
        result = self.inspect(data)
        self.assertEqual(result["metrics"]["missing_licences"], 1)
        self.assertEqual(result["policy"]["maximum_missing_licences"], 1)

    def test_readme_comes_from_the_validated_snapshot(self):
        report = self.inspect(rows())
        rendered = dataset_readme(ROOT / "README.dataset.md", self.config, report)
        self.assertIn(report["sha256"], rendered)
        self.assertIn("| opendata_catalog | 1 |", rendered)
        invalid = self.directory / "README.md"
        invalid.write_text("Missing fields", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "placeholder"):
            dataset_readme(invalid, self.config, report)

    def test_configuration_requires_all_fields_and_rejects_invalid_types(self):
        original = (ROOT / "publisher.example.toml").read_text(encoding="utf-8")
        target = self.directory / "publisher.toml"
        for source in (
            original.replace("maximum_missing_licences = 0\n", ""),
            original.replace(
                "maximum_structure_errors = 0", "maximum_structure_errors = true"
            ),
            original.replace("schema = 1", "schema = true"),
            original.replace(
                'archive = "open-data-catalogue.tar.gz"',
                'archive = "../archive.tar.gz"',
            ),
            original.replace("hour = 3", "hour = 24"),
        ):
            with self.subTest(source=source[:30]):
                target.write_text(source, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load(target)

    def test_concurrent_publisher_is_refused_without_removing_the_owner_lock(self):
        with publication_lock(self.directory):
            with (
                self.assertRaisesRegex(RuntimeError, "publisher lock exists"),
                publication_lock(self.directory),
            ):
                self.fail("another publisher entered")
            self.assertTrue((self.directory / ".publisher.lock").is_dir())
        self.assertFalse((self.directory / ".publisher.lock").exists())

    def test_schedule_has_explicit_paths_and_does_not_install_a_job(self):
        configured = copy.deepcopy(self.config)
        configured["schedule"]["log"] = self.directory / "logs" / "publisher.log"
        output = self.directory / "catalogue.plist"
        schedule(ROOT / "publisher.example.toml", configured, output)
        with output.open("rb") as stream:
            definition = plistlib.load(stream)
        self.assertEqual(definition["ProgramArguments"][-1], "prepare")
        self.assertNotIn("-lc", definition["ProgramArguments"])
        with self.assertRaises(FileExistsError):
            schedule(ROOT / "publisher.example.toml", configured, output)

    def test_cli_requires_configuration_and_never_assumes_publication(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "update")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("required", completed.stderr)


class Publication(unittest.TestCase):
    def test_only_the_returned_dataset_commit_can_be_pinned(self):
        hub = load(ROOT / "publisher.example.toml")["hub"]
        revision = "a" * 40
        prefix = f"{hub['endpoint']}/datasets/{hub['repository']}"
        self.assertEqual(
            revision_from_result(
                json.dumps({"url": f"{prefix}/commit/{revision}"}), hub
            ),
            revision,
        )
        self.assertIn(f"/resolve/{revision}/", file_url(hub, revision, hub["archive"]))
        for url in (
            f"{prefix}/commit/main",
            f"{prefix}/tree/main",
            f"{prefix}-other/commit/{revision}",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                revision_from_result(json.dumps({"url": url}), hub)
        with self.assertRaises(ValueError):
            file_url(hub, "main", hub["archive"])

    def test_remote_verification_reads_real_bytes_not_an_etag(self):
        payload = b"verified catalogue payload"

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *arguments):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/archive"
            digest = hashlib.sha256(payload).hexdigest()
            verify_download(url, digest, len(payload), 5)
            with self.assertRaises(RuntimeError):
                verify_download(url, "0" * 64, len(payload), 5)
            with self.assertRaises(RuntimeError):
                verify_download(url, digest, len(payload) - 1, 5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
