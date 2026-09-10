"""Historical reports remain immutable and cannot authorize a new export."""

import copy
import hashlib
import io
import json
import tarfile
import unittest

import test_documentation
from test_release import ROOT

from catalogue.archive import QualityError, inspect_archive
from catalogue.documentation import prepare, prepare_reported
from catalogue.documentation_evidence import current_status, read, status_path
from catalogue.publish import file_url


def historical_archive(path, report):
    with tarfile.open(path, "r:gz") as archive:
        payloads = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
    manifest = {key: report["manifest"][key] for key in ("taken_at", "tables")}
    manifest["schema_version"] = 1
    payloads["manifest.json"] = json.dumps(manifest).encode()
    with tarfile.open(path, "w:gz") as archive:
        for name, data in payloads.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return {**report, "manifest": manifest, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def evidence_pin(path, hub, revision, artifact):
    return {"path": str(path), "url": file_url(hub, revision, artifact), "revision": revision,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


class PublishedDocumentationTests(unittest.TestCase):
    close_server = test_documentation.DocumentationTests.close_server

    def setUp(self):
        test_documentation.DocumentationTests.setUp(self)
        try:
            inspect_archive(self.catalogue, self.config["quality"])
        except QualityError as error:
            report = error.report
        self.original_report = report
        report = historical_archive(self.catalogue, report)
        self.report = self.root / "catalogue-quality.json"
        self.report.write_text(json.dumps({"accepted": False, "policy": report["policy"], "report": report}, indent=2))
        self.evidence = self.root / "evidence.json"
        self.configuration = {"schema_version": 1,
            "archive": evidence_pin(self.catalogue, self.config["hub"], "a" * 40, "open-data-catalogue.tar.gz"),
            "quality_report": evidence_pin(self.report, self.config["hub"], "c" * 40, "catalogue-quality.json")}
        self.save_evidence()
        self.payloads["open-data-catalogue.tar.gz"] = self.catalogue.read_bytes()
        self.payloads["catalogue-quality.json"] = self.report.read_bytes()
        self.target = self.root / "reported-publication"
        self.target.mkdir()

    def save_evidence(self):
        self.evidence.write_text(json.dumps(self.configuration))

    def reseal_report(self):
        self.configuration["quality_report"] = evidence_pin(self.report, self.config["hub"], "c" * 40, "catalogue-quality.json")
        self.save_evidence()

    def prepare(self):
        return prepare_reported(self.target, self.config, self.evidence, "catalogue-status.json",
                                self.releases, ROOT / "README.hub.reported.md", ROOT / "viewer.json")

    def test_preserves_historical_report_and_separates_current_admission(self):
        self.prepare()
        self.assertEqual((self.target / "catalogue-quality.json").read_bytes(), self.report.read_bytes())
        status = json.loads((self.target / "catalogue-status.json").read_bytes())
        self.assertEqual(status["current_quality_evaluation"], "not_performed")
        self.assertFalse(status["admitted"])
        self.assertEqual(status["reason"], "snapshot_schema_mismatch")
        self.assertEqual(status["observed_snapshot_schema"], 1)
        self.assertEqual(status["required_snapshot_schema"], 2)
        self.assertEqual(status["quality_report"]["sha256"], self.configuration["quality_report"]["sha256"])
        card = (self.target / "README.md").read_text()
        self.assertIn("historical measurements", card)
        self.assertIn("no current quality evaluation", card)
        self.assertIn(self.configuration["quality_report"]["url"], card)
        self.assertIn(status["current_policy_sha256"], card)
        self.assertEqual(len(self.requests), 5)

    def test_old_archive_remains_rejected_by_current_release_inspector(self):
        with self.assertRaisesRegex(ValueError, "schema_version must be 2"):
            inspect_archive(self.catalogue, self.config["quality"])
        with self.assertRaisesRegex(ValueError, "schema_version must be 2"):
            prepare(self.target, self.config, self.catalogue, "a" * 40, self.releases,
                    ROOT / "README.hub.md", ROOT / "viewer.json")
        self.assertFalse(list(self.target.iterdir()))

    def test_different_current_policy_never_relabels_historical_metrics(self):
        original = self.report.read_bytes()
        self.config["quality"]["minimum_datasets"] += 1
        self.prepare()
        self.assertEqual((self.target / "catalogue-quality.json").read_bytes(), original)
        status = json.loads((self.target / "catalogue-status.json").read_text())
        historical = json.loads(original)
        self.assertNotEqual(status["current_policy"], historical["policy"])
        self.assertEqual(status["current_quality_evaluation"], "not_performed")
        self.assertFalse(status["admitted"])

    def test_schema_two_is_not_current_admission_from_format_alone(self):
        value = read(self.evidence, self.config, verify_remote=False)
        value["evidence"]["report"]["manifest"]["schema_version"] = 2
        status = current_status(value, self.config["quality"])
        self.assertFalse(status["admitted"])
        self.assertEqual(status["reason"], "current_quality_not_evaluated")
        changed = copy.deepcopy(self.config["quality"])
        changed["minimum_datasets"] += 1
        self.assertNotEqual(status["current_policy_sha256"], current_status(value, changed)["current_policy_sha256"])

    def test_local_tamper_is_rejected_before_remote_read_or_staging(self):
        for name in ("archive", "quality_report"):
            with self.subTest(name=name):
                self.configuration[name]["sha256"] = "0" * 64
                self.save_evidence()
                with self.assertRaisesRegex(ValueError, "local size or digest"):
                    self.prepare()
                self.assertFalse(list(self.target.iterdir()))
                self.configuration[name]["sha256"] = hashlib.sha256(
                    (self.catalogue if name == "archive" else self.report).read_bytes()).hexdigest()
        self.assertEqual(self.requests, [])

    def test_remote_report_tamper_is_rejected_before_staging(self):
        self.payloads["catalogue-quality.json"] = b"different"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.prepare()
        self.assertFalse(list(self.target.iterdir()))

    def test_resealed_report_with_wrong_archive_or_manifest_is_rejected(self):
        original = json.loads(self.report.read_bytes())
        for field in ("sha256", "manifest", "policy"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                if field == "sha256":
                    changed["report"][field] = "0" * 64
                elif field == "manifest":
                    changed["report"][field]["taken_at"] = "2026-01-02T00:00:00Z"
                else:
                    changed["report"][field]["minimum_datasets"] += 1
                self.report.write_text(json.dumps(changed))
                self.reseal_report()
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse(list(self.target.iterdir()))
        self.assertEqual(self.requests, [])

    def test_evidence_schema_and_immutable_identity_are_required(self):
        original = copy.deepcopy(self.configuration)
        for mutation in ("schema", "unknown", "branch", "repository", "artifact"):
            with self.subTest(mutation=mutation):
                self.configuration = copy.deepcopy(original)
                if mutation == "schema":
                    self.configuration["schema_version"] = True
                elif mutation == "unknown":
                    self.configuration["accepted"] = True
                elif mutation == "branch":
                    self.configuration["archive"]["revision"] = "main"
                elif mutation == "repository":
                    self.configuration["quality_report"]["url"] = self.configuration["quality_report"]["url"].replace("/datasets/", "/other/")
                else:
                    self.configuration["quality_report"]["url"] = self.configuration["archive"]["url"]
                self.save_evidence()
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse(list(self.target.iterdir()))
        self.assertEqual(self.requests, [])

    def test_status_path_and_template_are_explicit(self):
        for value in ("../status.json", "catalogue-quality.json", "viewer-manifest.json", "README.md"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                status_path(value)
        with self.assertRaisesRegex(ValueError, "every artifact placeholder"):
            prepare_reported(self.target, self.config, self.evidence, "status.json", self.releases,
                             ROOT / "README.hub.md", ROOT / "viewer.json")
        self.assertFalse(list(self.target.iterdir()))
