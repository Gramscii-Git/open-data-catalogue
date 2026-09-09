"""Publisher scope verification and native virtual-environment execution."""

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import venv
from datetime import UTC, datetime
from pathlib import Path

from test_availability import archive_at, tables

from catalogue.availability import inspect_availability, policy_from
from catalogue.availability_build import verify_build
from catalogue.availability_publish import prepare as prepare_publication
from catalogue.config import load

ROOT = Path(__file__).resolve().parents[1]


class AvailabilityBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.policy = policy_from(ROOT / "availability-policy.example.toml")
        self.policy.update(providers=["source"], staging_directory=self.root / "validation")
        self.spec = {"datasets": [{
            "provider": "source", "dataset_id": "observations", "arguments": {"territory": "A"},
            "varying": {"year": [2020]}, "when": "always",
        }]}

    def archive(self, spec):
        content = tables()
        request = {"arguments": {"dataset": "observations", "territory": "A", "year": 2020}, "when": "always"}
        partition = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        content["partitions.jsonl"][0].update(id=partition, request=request)
        content["datasets.jsonl"][0].update(
            partitions=[partition], scope={"request_grid": spec["datasets"][0], "consistency": "per-response"},
        )
        content["combinations.jsonl"][0]["partition"] = partition
        return archive_at(self.root / "availability.tar.gz", content)

    def test_exact_scope_is_verified_against_real_archive_bytes(self):
        archive = self.archive(self.spec)
        exported = inspect_availability(archive, self.policy)
        result = verify_build(archive, exported, self.spec, self.policy)
        self.assertEqual(result["tables"]["combinations.jsonl"], 1)

    def publication(self, now, destination="availability"):
        archive = self.archive(self.spec)
        report = inspect_availability(archive, self.policy)
        (self.root / "scope.json").write_text(json.dumps(self.spec))
        (self.root / "inventories.json").write_text(json.dumps({"schema_version": 1, "inventories": {}, "bindings": []}))
        (self.root / "quality.json").write_text(json.dumps(report))
        policy = self.root / "policy.toml"
        policy.write_text((ROOT / "availability-policy.example.toml").read_text().replace(
            'providers = ["dvns", "cruscotto"]', 'providers = ["source"]',
        ))
        return prepare_publication(
            self.root, self.root / "publication", destination, policy,
            ROOT / "README.availability.md", now=now,
        )

    def test_publication_includes_only_validated_files_in_its_own_directory(self):
        report, files = self.publication(datetime(2026, 9, 8, 13, tzinfo=UTC))
        self.assertEqual(len(files), 7)
        self.assertTrue(all(name.startswith("availability/") for name in files))
        target = self.root / "publication" / "availability"
        self.assertEqual(hashlib.sha256((target / "availability.tar.gz").read_bytes()).hexdigest(), report["sha256"])
        self.assertFalse((self.root / "publication" / "manifest.json").exists())

    def test_publication_rejects_expired_source_evidence(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            self.publication(datetime(2026, 9, 10, tzinfo=UTC))
        self.assertFalse((self.root / "publication").exists())

    def test_publication_cannot_escape_its_repository_directory(self):
        with self.assertRaisesRegex(ValueError, "relative repository"):
            self.publication(datetime(2026, 9, 8, 13, tzinfo=UTC), "../outside")

    def test_scope_label_does_not_excuse_missing_requested_partitions(self):
        self.spec["datasets"][0]["varying"]["year"].append(2022)
        archive = self.archive(self.spec)
        exported = inspect_availability(archive, self.policy)
        with self.assertRaisesRegex(ValueError, "publisher-requested partitions"):
            verify_build(archive, exported, self.spec, self.policy)

    def test_a_different_dataset_scope_is_rejected(self):
        archive = self.archive(self.spec)
        exported = inspect_availability(archive, self.policy)
        wrong = copy.deepcopy(self.spec)
        wrong["datasets"][0]["arguments"]["territory"] = "B"
        with self.assertRaisesRegex(ValueError, "exact dataset scope"):
            verify_build(archive, exported, wrong, self.policy)

    def test_producer_digest_cannot_replace_archive_verification(self):
        archive = self.archive(self.spec)
        exported = inspect_availability(archive, self.policy)
        exported["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "producer sha256"):
            verify_build(archive, exported, self.spec, self.policy)

    def test_python_launcher_retains_its_virtual_environment(self):
        builder = venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt")
        directory = self.root / "harvester environment"
        builder.create(directory)
        executable = builder.ensure_directories(directory).env_exe
        template = (ROOT / "publisher.example.toml").read_text()
        template = template.replace(
            'python = "../semantic-deterministic-graph/server/.venv/bin/python"',
            "python = " + json.dumps(executable),
        )
        path = self.root / "publisher.toml"
        path.write_text(template)
        config = load(path)
        completed = subprocess.run(
            [str(config["deployment"]["python"]), "-c", "import sys; print(sys.prefix)"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(Path(completed.stdout.strip()).resolve(), directory.resolve())
        self.assertEqual(config["schedule"]["python"], config["deployment"]["python"])

    def test_deployment_environment_location_is_required(self):
        template = (ROOT / "publisher.example.toml").read_text()
        path = self.root / "publisher.toml"
        path.write_text("\n".join(line for line in template.splitlines() if not line.startswith("environment_file =")))
        with self.assertRaisesRegex(ValueError, "environment_file"):
            load(path)
