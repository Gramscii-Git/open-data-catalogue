"""Release gates for independently verified joint-availability artifacts."""

import copy
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from catalogue.availability import MEMBERS, inspect_availability, policy_from

ROOT = Path(__file__).resolve().parents[1]


def tables():
    identity = {"provider": "source", "dataset_id": "observations"}
    request = {"territories": ["A", "B"]}
    partition = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = {
        "method": "GET",
        "url": "https://example.org/observations",
        "request_sha256": "a" * 64,
        "status": 200,
        "bytes": 100,
        "wire_bytes": 100,
        "sha256": "b" * 64,
        "observed_at": "2026-09-08T12:00:00Z",
        "etag": None,
        "last_modified": None,
    }
    return {
        "datasets.jsonl": [
            {
                **identity,
                "title": "Source observations",
                "scope": {"territories": ["A", "B"]},
                "definition_sha256": "c" * 64,
                "period_kind": "calendar",
                "axes": ["measure", "unit"],
                "partitions": [partition],
                "verified_at": "2026-09-08T12:00:00Z",
                "valid_until": "2026-09-09T12:00:00Z",
            }
        ],
        "partitions.jsonl": [
            {
                **identity,
                "id": partition,
                "complete": True,
                "request": request,
                "receipts": [receipt],
            }
        ],
        "combinations.jsonl": [
            {
                **identity,
                "partition": partition,
                "presence": "observed",
                "period": {
                    "id": "2020",
                    "label": "2020",
                    "start": "2020-01-01T00:00:00Z",
                    "end": "2020-12-31T23:59:59Z",
                },
                "territory": {"code": "A", "label": "Territory A", "level": "region"},
                "dimensions": {
                    "measure": {"code": "count", "label": "Count"},
                    "unit": {"code": "persons", "label": "Persons"},
                },
            }
        ],
    }


def archive_at(path, content, *, declared=None, extra=None):
    manifest = {
        "schema_version": 1,
        "taken_at": "2026-09-08T12:01:00Z",
        "tables": {name: len(content[name]) for name in MEMBERS}
        if declared is None
        else declared,
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, rows in {"manifest.json": [manifest], **content}.items():
            body = "".join(json.dumps(row) + "\n" for row in rows).encode()
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
        if extra is not None:
            member = tarfile.TarInfo(extra)
            archive.addfile(member, io.BytesIO())
    return path


class AvailabilityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.policy = {
            **policy_from(ROOT / "availability-policy.example.toml"),
            "providers": ["source"],
            "staging_directory": self.root / "validation",
        }

    def inspect(self, content, **kwargs):
        path = archive_at(self.root / "index.tar.gz", content, **kwargs)
        return inspect_availability(path, self.policy)

    def test_complete_joint_evidence_passes_without_retaining_validation_database(self):
        report = self.inspect(tables())
        self.assertEqual(report["tables"]["combinations.jsonl"], 1)
        self.assertEqual(len(report["sha256"]), 64)
        self.assertEqual(list(self.policy["staging_directory"].iterdir()), [])

    def test_non_geographic_observations_preserve_their_explicit_null_territory(self):
        content = tables()
        content["combinations.jsonl"][0]["territory"] = None
        report = self.inspect(content)
        self.assertEqual(report["tables"]["combinations.jsonl"], 1)
        duplicate = copy.deepcopy(content["combinations.jsonl"][0])
        duplicate["presence"] = "missing"
        content["combinations.jsonl"].append(duplicate)
        with self.assertRaises(sqlite3.IntegrityError):
            self.inspect(content)

    def test_missing_territory_or_incomplete_geography_cannot_be_invented(self):
        for territory in ({}, {"code": "A", "label": "Territory A", "level": None}):
            with self.subTest(territory=territory):
                content = tables()
                content["combinations.jsonl"][0]["territory"] = territory
                with self.assertRaises(ValueError):
                    self.inspect(content)
        content = tables()
        del content["combinations.jsonl"][0]["territory"]
        with self.assertRaises(ValueError):
            self.inspect(content)

    def test_geographic_contract_is_consistent_within_each_dataset(self):
        content = tables()
        non_geographic = copy.deepcopy(content["combinations.jsonl"][0])
        non_geographic["territory"] = None
        content["combinations.jsonl"].append(non_geographic)
        with self.assertRaisesRegex(ValueError, "mixes geographic"):
            self.inspect(content)
        for name in MEMBERS:
            original = copy.deepcopy(content[name][0])
            original["dataset_id"] = "exchange_rates"
            if name == "combinations.jsonl":
                original["territory"] = None
                content[name].pop()
            content[name].append(original)
        self.assertEqual(self.inspect(content)["tables"]["combinations.jsonl"], 2)

    def test_missing_null_and_suppressed_states_are_not_collapsed(self):
        content = tables()
        for index, state in enumerate(["missing", "suppressed"], 1):
            item = copy.deepcopy(content["combinations.jsonl"][0])
            item["territory"]["code"] = f"T{index}"
            item["presence"] = state
            content["combinations.jsonl"].append(item)
        self.assertEqual(self.inspect(content)["tables"]["combinations.jsonl"], 3)

    def test_incomplete_partition_cannot_be_published(self):
        content = tables()
        content["partitions.jsonl"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.inspect(content)

    def test_missing_declared_partition_cannot_be_published(self):
        content = tables()
        content["datasets.jsonl"][0]["partitions"].append("d" * 64)
        with self.assertRaisesRegex(ValueError, "incomplete partitions"):
            self.inspect(content)

    def test_combination_requires_existing_dataset_and_partition(self):
        for field in ("dataset_id", "partition"):
            with self.subTest(field=field):
                content = tables()
                content["combinations.jsonl"][0][field] = "unknown"
                with self.assertRaisesRegex(
                    ValueError, "invalid partition|no verified combinations"
                ):
                    self.inspect(content)

    def test_dimension_marginals_cannot_replace_joint_combinations(self):
        content = tables()
        del content["combinations.jsonl"][0]["dimensions"]["unit"]
        with self.assertRaisesRegex(ValueError, "dimension set"):
            self.inspect(content)

    def test_a_different_completed_request_does_not_satisfy_the_declared_partition(
        self,
    ):
        content = tables()
        content["partitions.jsonl"][0]["request"] = {"territories": ["A"]}
        with self.assertRaisesRegex(ValueError, "declared request"):
            self.inspect(content)
        content = tables()
        content["datasets.jsonl"][0]["partitions"] = ["d" * 64]
        with self.assertRaisesRegex(ValueError, "invalid partition"):
            self.inspect(content)

    def test_duplicate_combination_is_rejected_even_if_presence_differs(self):
        content = tables()
        copied = copy.deepcopy(content["combinations.jsonl"][0])
        copied["presence"] = "missing"
        content["combinations.jsonl"].append(copied)
        with self.assertRaises(sqlite3.IntegrityError):
            self.inspect(content)

    def test_calendar_period_cannot_be_an_unbounded_source_label(self):
        content = tables()
        content["combinations.jsonl"][0]["period"].update(start=None, end=None)
        with self.assertRaisesRegex(ValueError, "period"):
            self.inspect(content)
        content["datasets.jsonl"][0]["period_kind"] = "source-label"
        self.inspect(content)

    def test_unsuccessful_receipt_never_establishes_an_option(self):
        content = tables()
        content["partitions.jsonl"][0]["receipts"][0]["status"] = 429
        with self.assertRaisesRegex(ValueError, "successful source reads"):
            self.inspect(content)

    def test_verification_time_must_retain_the_oldest_source_read(self):
        content = tables()
        content["datasets.jsonl"][0]["verified_at"] = "2026-09-08T12:00:30Z"
        with self.assertRaisesRegex(ValueError, "timestamps"):
            self.inspect(content)
        content["datasets.jsonl"][0]["verified_at"] = "2026-09-08T14:00:00+02:00"
        self.inspect(content)
        receipt = copy.deepcopy(content["partitions.jsonl"][0]["receipts"][0])
        receipt["observed_at"] = "2026-09-08T11:59:00Z"
        content["partitions.jsonl"][0]["receipts"].append(receipt)
        with self.assertRaisesRegex(ValueError, "timestamps"):
            self.inspect(content)

    def test_receipts_cannot_come_from_after_the_snapshot(self):
        content = tables()
        receipt = copy.deepcopy(content["partitions.jsonl"][0]["receipts"][0])
        receipt["observed_at"] = "2026-09-08T12:02:00Z"
        content["partitions.jsonl"][0]["receipts"].append(receipt)
        with self.assertRaisesRegex(ValueError, "timestamps"):
            self.inspect(content)

    def test_snapshot_cannot_contain_expired_availability(self):
        content = tables()
        content["datasets.jsonl"][0]["valid_until"] = "2026-09-08T12:01:00Z"
        with self.assertRaisesRegex(ValueError, "expire before the snapshot"):
            self.inspect(content)

    def test_cli_reports_duplicate_records_without_an_unhandled_traceback(self):
        content = tables()
        content["combinations.jsonl"].append(
            copy.deepcopy(content["combinations.jsonl"][0])
        )
        archive = archive_at(self.root / "index.tar.gz", content)
        policy = self.root / "policy.toml"
        policy.write_text(
            (ROOT / "availability-policy.example.toml")
            .read_text(encoding="utf-8")
            .replace('providers = ["dvns", "cruscotto"]', 'providers = ["source"]'),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "update"),
                "--config",
                str(ROOT / "publisher.example.toml"),
                "check-availability",
                "--archive",
                str(archive),
                "--policy",
                str(policy),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("UNIQUE constraint failed", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_values_are_not_part_of_the_availability_artifact(self):
        content = tables()
        content["combinations.jsonl"][0]["value"] = 42
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.inspect(content)

    def test_archive_counts_and_members_are_exact(self):
        with self.assertRaisesRegex(ValueError, "counts"):
            self.inspect(tables(), declared=dict.fromkeys(MEMBERS, 0))
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.inspect(tables(), extra="../outside")

    def test_unpacked_line_and_database_budgets_are_enforced(self):
        original = dict(self.policy)
        for limit, value, error in [
            ("max_unpacked_bytes", 64, ValueError),
            ("max_line_bytes", 32, ValueError),
            ("max_rows", 1, ValueError),
            ("max_database_bytes", 4096, sqlite3.OperationalError),
        ]:
            with self.subTest(limit=limit):
                self.policy = {**original, limit: value}
                with self.assertRaises(error):
                    self.inspect(tables())


if __name__ == "__main__":
    unittest.main()
