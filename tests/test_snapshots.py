"""Immutable source publications must match every original indexed response."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_availability import archive_at, tables

from catalogue.availability import policy_from
from catalogue.snapshots import inspect

ROOT = Path(__file__).resolve().parents[1]


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "snapshots"
        (self.directory / "responses").mkdir(parents=True)
        content = tables()
        self.availability = archive_at(self.root / "availability.tar.gz", content)
        self.policy = policy_from(ROOT / "availability-policy.example.toml")
        self.policy.update(providers=["source"], staging_directory=self.root / "validation")
        self.source = content["partitions.jsonl"][0]["receipts"][0]
        self.bundle = {"schema_version": 1, "responses": {self.source["sha256"]: {
            "schema_version": 1, "provider": "source", "source": self.source.copy(), "payload": {"observations": [10]},
        }}}
        self.manifest = {"schema_version": 1, "availability_sha256": hashlib.sha256(self.availability.read_bytes()).hexdigest(),
                         "providers": {"source": {"observations": "c" * 64}}, "responses": {},
                         "projections": {"source": {"identity_fields": [], "datasets": {"observations": {
                             "licence": "CC BY 4.0", "attribution": "Source", "source_url": "https://example.org/observations",
                             "fields": ["observations"],
                         }}}}}

    def write(self):
        body = json.dumps(self.bundle).encode()
        digest = hashlib.sha256(body).hexdigest()
        (self.directory / f"responses/{digest}.json").write_bytes(body)
        self.manifest["responses"] = {self.source["sha256"]: {"sha256": digest, "bytes": len(body)}}
        self.save_manifest()

    def save_manifest(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def test_every_asset_and_native_receipt_is_independently_verified(self):
        self.write()
        result = inspect(self.directory, self.availability, self.policy)
        self.assertEqual(result["responses"], 1)
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(result["availability_sha256"], self.manifest["availability_sha256"])

    def test_changed_source_body_is_not_publishable(self):
        self.write()
        file = next((self.directory / "responses").iterdir())
        file.write_bytes(file.read_bytes().replace(b"10", b"11"))
        with self.assertRaisesRegex(ValueError, "content digest"):
            inspect(self.directory, self.availability, self.policy)

    def test_missing_asset_is_not_publishable(self):
        self.write()
        next((self.directory / "responses").iterdir()).unlink()
        with self.assertRaisesRegex(ValueError, "missing or undeclared"):
            inspect(self.directory, self.availability, self.policy)

    def test_undeclared_response_files_are_not_uploaded(self):
        self.write()
        (self.directory / "unlicensed.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "missing or undeclared"):
            inspect(self.directory, self.availability, self.policy)

    def test_another_index_cannot_authorize_source_snapshots(self):
        self.write()
        self.manifest["availability_sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "different availability"):
            inspect(self.directory, self.availability, self.policy)

    def test_changed_projection_definition_is_not_publishable(self):
        self.write()
        self.manifest["providers"]["source"]["observations"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "definitions differ"):
            inspect(self.directory, self.availability, self.policy)

    def test_omitted_source_receipt_is_not_publishable(self):
        self.write()
        self.manifest["responses"] = {}
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "omit or add"):
            inspect(self.directory, self.availability, self.policy)

    def test_forged_original_read_time_is_not_publishable(self):
        self.bundle["responses"][self.source["sha256"]]["source"]["observed_at"] = "2026-09-09T12:00:00Z"
        self.write()
        with self.assertRaisesRegex(ValueError, "indexed native receipt"):
            inspect(self.directory, self.availability, self.policy)

    def test_unbound_response_cannot_hide_inside_a_valid_shard(self):
        self.bundle["responses"]["0" * 64] = self.bundle["responses"].pop(self.source["sha256"])
        self.write()
        with self.assertRaisesRegex(ValueError, "unbound or repeated"):
            inspect(self.directory, self.availability, self.policy)

    def test_response_budget_is_enforced_before_loading_assets(self):
        self.write()
        self.manifest["responses"][self.source["sha256"]]["bytes"] = self.policy["max_line_bytes"] + 1
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "byte budget"):
            inspect(self.directory, self.availability, self.policy)

    def test_undeclared_payload_fields_are_not_publishable(self):
        self.bundle["responses"][self.source["sha256"]]["payload"]["unlicensed"] = [11]
        self.write()
        with self.assertRaisesRegex(ValueError, "unlicensed projection"):
            inspect(self.directory, self.availability, self.policy)

    def test_missing_licence_is_not_publishable(self):
        self.manifest["projections"]["source"]["datasets"]["observations"]["licence"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "licence"):
            inspect(self.directory, self.availability, self.policy)
