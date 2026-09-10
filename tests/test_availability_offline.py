"""Offline publication must preserve pinned source evidence and its lifetime."""

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from test_availability import archive_at, tables

from catalogue.availability import policy_from
from catalogue.availability_offline import Inputs, inspect_inputs, load_manifest

ROOT = Path(__file__).resolve().parents[1]


class OfflineProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = datetime(2026, 9, 8, 13, tzinfo=UTC)
        self.policy = policy_from(ROOT / "availability-policy.example.toml")
        self.policy.update(providers=["source"], staging_directory=self.root / "validation")
        self.scope = {"datasets": [{"provider": "source", "dataset_id": "observations", "arguments": {}, "varying": {}, "when": "2020"}]}
        request = {"arguments": {"dataset": "observations"}, "when": "2020"}
        partition = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.original = tables()
        self.original["datasets.jsonl"][0].update(partitions=[partition], scope={"request_grid": self.scope["datasets"][0], "consistency": "per-response"})
        self.original["partitions.jsonl"][0].update(id=partition, request=request)
        self.original["combinations.jsonl"][0]["partition"] = partition
        self.candidate = copy.deepcopy(self.original)
        self.candidate["datasets.jsonl"][0]["definition_sha256"] = "d" * 64
        self.native = b'<Structure xmlns="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"/>'
        self.receipt = {"case": "native-graph", "method": "GET", "url": "https://example.org/dataflow/source/observations/1.0?references=descendants",
                        "observed_at": "2026-09-08T12:30:00Z", "status": 200,
                        "content_type": "application/vnd.sdmx.structure+xml;version=2.1", "bytes": len(self.native), "sha256": hashlib.sha256(self.native).hexdigest()}
        self.plan = {"schema_version": 1, "kind": "sdmx-native-graph-reprojection", "timeout_seconds": 30,
                     "scope": self.asset("scope.json", json.dumps(self.scope).encode()),
                     "inventories": self.asset("inventories.json", b'{"schema_version":1,"inventories":{},"bindings":[]}'),
                     "configuration": {}, "capture": {}, "core": {},
                     "graphs": [{"provider": "source", "dataset_id": "observations",
                                 "receipt": self.asset("graph.json", json.dumps(self.receipt).encode()), "body": self.asset("graph.xml", self.native)}],
                     "definitions": [{"provider": "source", "dataset_id": "observations", "original": "c" * 64, "candidate": "d" * 64}]}
        self.repack()

    def asset(self, name, body):
        (self.root / name).write_bytes(body)
        return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def repack(self):
        for name, content, clock in (("original", self.original, "2026-09-08T12:01:00Z"), ("candidate", self.candidate, "2026-09-08T12:45:00Z")):
            file = archive_at(self.root / f"{name}.tar.gz", content, taken_at=clock)
            self.plan[name] = {"path": file.name, "bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}

    def seal(self):
        path = self.root / "provenance.json"
        body = json.dumps(self.plan).encode()
        path.write_bytes(body)
        return path, hashlib.sha256(body).hexdigest()

    def inspect(self):
        return inspect_inputs(*self.seal(), self.policy, now=self.now)

    def test_pinned_archives_and_graph_receipt_preserve_clocks(self):
        state = self.inspect()
        self.assertEqual(state["report"]["tables"]["combinations.jsonl"], 1)
        self.assertEqual(state["graphs"]["source", "observations"]["receipt"], self.receipt)
        self.assertEqual(state["datasets"]["source", "observations"]["valid_until"], "2026-09-09T12:00:00Z")

    def test_graph_body_tampering_is_rejected_before_projection(self):
        (self.root / "graph.xml").write_bytes(self.native.replace(b"Structure", b"Strukture"))
        with self.assertRaisesRegex(ValueError, "pinned content digest"):
            self.inspect()

    def test_graph_receipt_cannot_be_changed_under_the_original_pin(self):
        path = self.root / "graph.json"
        path.write_bytes(path.read_bytes().replace(b"12:30", b"12:31"))
        with self.assertRaisesRegex(ValueError, "pinned content digest"):
            self.inspect()

    def test_resealed_body_must_still_match_its_native_receipt(self):
        self.plan["graphs"][0]["body"] = self.asset("graph.xml", self.native + b" ")
        with self.assertRaisesRegex(ValueError, "original receipt"):
            self.inspect()

    def test_no_ttl_extension_even_with_resealed_candidate(self):
        self.candidate["datasets.jsonl"][0]["valid_until"] = "2026-09-10T12:00:00Z"
        self.repack()
        with self.assertRaisesRegex(ValueError, "source clocks, lifetime"):
            self.inspect()

    def test_preserved_partitions_cannot_be_relabelled_as_new_reads(self):
        self.candidate["partitions.jsonl"][0]["receipts"][0]["etag"] = "different"
        self.repack()
        with self.assertRaisesRegex(ValueError, "original partitions"):
            self.inspect()

    def test_same_counts_do_not_authorize_changed_observation_coordinates(self):
        self.candidate["combinations.jsonl"][0]["territory"]["code"] = "B"
        self.repack()
        with self.assertRaisesRegex(ValueError, "observation combinations"):
            self.inspect()

    def test_expired_evidence_cannot_be_renewed_by_validation(self):
        self.now = datetime(2026, 9, 10, tzinfo=UTC)
        with self.assertRaisesRegex(ValueError, "expired"):
            self.inspect()

    def test_graph_clock_cannot_follow_candidate_assembly(self):
        self.receipt["observed_at"] = "2026-09-08T12:59:00Z"
        self.plan["graphs"][0]["receipt"] = self.asset("graph.json", json.dumps(self.receipt).encode())
        with self.assertRaisesRegex(ValueError, "graph clock"):
            self.inspect()

    def test_graph_clock_cannot_precede_preserved_verification(self):
        self.receipt["observed_at"] = "2026-09-08T11:59:00Z"
        self.plan["graphs"][0]["receipt"] = self.asset("graph.json", json.dumps(self.receipt).encode())
        with self.assertRaisesRegex(ValueError, "graph clock"):
            self.inspect()

    def test_candidate_definition_must_match_the_explicit_manifest(self):
        self.plan["definitions"][0]["candidate"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "explicit declaration"):
            self.inspect()

    def test_exact_graph_set_is_required(self):
        self.plan["graphs"] = []
        with self.assertRaisesRegex(ValueError, "omits a native graph"):
            self.inspect()

    def test_input_manifest_pin_is_not_an_optional_hint(self):
        path, pin = self.seal()
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "explicit digest pin"):
            load_manifest(path, pin, self.policy)

    def test_inputs_cannot_escape_the_explicit_bundle(self):
        self.plan["graphs"][0]["body"]["path"] = "../graph.xml"
        with self.assertRaisesRegex(ValueError, "canonical relative"):
            self.inspect()

    def test_symlink_input_is_not_accepted_as_an_original(self):
        (self.root / "linked.xml").symlink_to(self.root / "graph.xml")
        asset = {**self.plan["graphs"][0]["body"], "path": "linked.xml"}
        with self.assertRaisesRegex(ValueError, "cannot escape"):
            Inputs(self.root, self.policy).read(asset)

    def test_total_input_budget_is_checked(self):
        self.policy["max_unpacked_bytes"] = self.plan["original"]["bytes"] + self.plan["candidate"]["bytes"] - 1
        with self.assertRaisesRegex(ValueError, "total byte budget"):
            self.inspect()


class OfflineCoreIdentityTests(unittest.TestCase):
    def setUp(self):
        import subprocess

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "server/sdg").mkdir(parents=True)
        self.module = self.root / "server/sdg/__init__.py"
        self.module.write_text('"""Declared core fixture."""\n')
        (self.root / ".gitignore").write_text("ignored-assets/\n")
        for command in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false", "commit", "-qm", "Declare core"]):
            subprocess.run(command, cwd=self.root, check=True, capture_output=True)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()
        self.declaration = {"revision": revision, "files": {"__init__.py": hashlib.sha256(self.module.read_bytes()).hexdigest()}}

    def test_commit_blobs_and_filesystem_both_match_the_declared_core(self):
        from catalogue.availability_offline import core_identity

        self.assertEqual(core_identity(self.root, self.declaration), self.declaration)

    def test_uncommitted_code_cannot_be_relabelled_as_head_with_adjusted_pins(self):
        from catalogue.availability_offline import core_identity

        self.module.write_text('"""Changed code without a new commit."""\n')
        self.declaration["files"]["__init__.py"] = hashlib.sha256(self.module.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "commit blobs"):
            core_identity(self.root, self.declaration)

    def test_untracked_python_code_cannot_be_added_to_the_commit_manifest(self):
        from catalogue.availability_offline import core_identity

        added = self.module.with_name("extra.py")
        added.write_text('"""Uncommitted module."""\n')
        self.declaration["files"]["extra.py"] = hashlib.sha256(added.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "commit blobs"):
            core_identity(self.root, self.declaration)

    def test_unrelated_ignored_assets_do_not_invalidate_the_core(self):
        from catalogue.availability_offline import core_identity

        assets = self.root / "ignored-assets"
        assets.mkdir()
        (assets / "model.bin").write_bytes(b"asset")
        self.assertEqual(core_identity(self.root, self.declaration), self.declaration)

    def test_sdg_module_from_outside_the_declared_core_is_rejected(self):
        import types

        from catalogue.availability_offline import imported_core_files

        foreign = self.root / "foreign.py"
        foreign.write_text('"""Foreign module."""\n')
        module = types.ModuleType("sdg.foreign")
        module.__file__ = str(foreign)
        with self.assertRaisesRegex(ValueError, "outside the declared core"):
            imported_core_files(self.root, self.declaration["files"], {"sdg.foreign": module})
