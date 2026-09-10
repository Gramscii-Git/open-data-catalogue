"""Scheduled update contracts preserve remote evidence, active pins and failures."""

import copy
import hashlib
import http.server
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from test_availability import archive_at, tables
from test_release import rows, write_archive

from catalogue.availability import inspect_availability, policy_from
from catalogue.cli import prepare as prepare_catalogue
from catalogue.cli import schedule
from catalogue.config import load as load_config
from catalogue.publish import file_url
from catalogue.runtime import remaining
from catalogue.update_plan import load as load_plan
from catalogue.update_plan import load_state
from catalogue.update_run import require_fresh, run, state_lock, write_json

ROOT = Path(__file__).resolve().parents[1]


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.hub = self.root / "hub"
        self.hub.mkdir()
        self.requests = []
        self.corrupt = None
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                path = owner.hub / self.path.lstrip("/")
                filename = self.path.split("/resolve/", 1)[1].split("/", 1)[1]
                payload = b"changed remote bytes" if filename == owner.corrupt else path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.config = load_config(ROOT / "publisher.example.toml")
        self.config["hub"]["endpoint"] = f"http://127.0.0.1:{self.server.server_port}"
        self.config["deployment"]["build"] = self.root / "build"
        self.config["deployment"]["hf"] = [sys.executable, str(ROOT / "tests/fixtures/publication_cli.py"),
                                               "--root", str(self.hub), "--endpoint", self.config["hub"]["endpoint"]]
        self.config["quality"].update(minimum_datasets=1, providers={"sample": {"languages": ["en"], "vocabulary": True}})
        self.policy = self.root / "policy.toml"
        self.policy.write_text((ROOT / "availability-policy.example.toml").read_text().replace(
            'providers = ["dvns", "cruscotto"]', 'providers = ["source"]'))
        self.scope = self.root / "scope.json"
        self.spec = {"schema_version": 2, "inventories": {}, "limits": {"operation_timeout_seconds": 5}, "datasets": [{
            "provider": "source", "dataset_id": "observations", "arguments": {"territory": "A"},
            "varying": {"year": [2020]}, "when": "always", "valid_for_seconds": 86400,
        }]}
        self.scope.write_text(json.dumps(self.spec))
        self.viewer = self.root / "viewer.json"
        viewer = json.loads((ROOT / "viewer.json").read_text())
        viewer["tables"] = [row for row in viewer["tables"] if row["archive"] in {"catalogue", "national"}]
        self.viewer.write_text(json.dumps(viewer))
        self.catalogue = self.root / "catalogue.tar.gz"
        write_archive(self.catalogue, rows())
        self.archive = self.root / "initial.tar.gz"
        self.content = tables()
        archive_at(self.archive, self.content)
        catalogue_pub = self.initial_publication(self.catalogue, self.config["hub"]["archive"], "a" * 40)
        availability_pub = self.initial_publication(self.archive, "availability/availability.tar.gz", "b" * 40)
        self.active = {"indexes": {"national": {"artifact": self.pin(availability_pub), "snapshots": {}}}}
        self.activation = self.root / "initial-activation.json"
        self.activation.write_text(json.dumps({"activated": True, "index": "national", **self.active["indexes"]["national"]}))
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps({"schema_version": 1, "catalogue": {
            "archive": str(self.catalogue), "publication": catalogue_pub["path"],
        }, "indexes": {"national": {
            "archive": str(self.archive), "publication": availability_pub["path"], "activation": str(self.activation),
            "policy": str(self.policy), "destination": "availability",
        }}}))
        self.plan = {"schema_version": 1, "state": str(self.state), "cadence": {
            "interval_seconds": 3600, "maximum_run_seconds": 300, "minimum_remaining_seconds": 60,
        }, "discovery": {"action": "retain"}, "indexes": {"national": {
            "scope": str(self.scope), "policy": str(self.policy), "destination": "availability",
            "readme_template": str(ROOT / "README.availability.md"), "snapshots": None,
        }}, "documentation": {"readme_template": str(ROOT / "README.hub.md"), "viewer_config": str(self.viewer)}}
        self.plan_path = self.root / "plan.json"
        self.harvester_calls = []
        self.fail_activation = False
        self.source_age = timedelta(0)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def initial_publication(self, source, destination, revision):
        target = self.hub / "datasets" / self.config["hub"]["repository"] / "resolve" / revision / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        report = {"revision": revision, "url": file_url(self.config["hub"], revision, destination),
                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "bytes": source.stat().st_size, "verified": True}
        path = self.root / f"publication-{revision}.json"
        path.write_text(json.dumps(report))
        return {**report, "path": str(path)}

    @staticmethod
    def pin(receipt):
        return {key: receipt[key] for key in ("url", "revision", "sha256", "bytes")}

    def configured(self):
        self.plan_path.write_text(json.dumps(self.plan))
        return load_plan(self.plan_path, self.config)

    def harvester(self, config, *arguments, capture=False):
        self.harvester_calls.append(arguments)
        action = arguments[0]
        if action == "availability-status":
            return json.dumps(self.active)
        if action in {"--availability-contract", "--release-contract"}:
            return "1"
        if action == "index-availability":
            source = Path(arguments[arguments.index("--to") + 1])
            source.mkdir()
            specification = json.loads(Path(arguments[arguments.index("--spec") + 1]).read_bytes())
            content = tables()
            request = {"arguments": {"dataset": "observations", "territory": "A", "year": 2020}, "when": "always"}
            partition = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            now = datetime.now(UTC)
            observed = now - self.source_age
            content["partitions.jsonl"][0].update(id=partition, request=request)
            content["partitions.jsonl"][0]["receipts"][0]["observed_at"] = observed.isoformat()
            content["datasets.jsonl"][0].update(partitions=[partition], verified_at=observed.isoformat(),
                valid_until=(observed + timedelta(seconds=specification["datasets"][0]["valid_for_seconds"])).isoformat(),
                scope={"request_grid": specification["datasets"][0], "consistency": "per-response"})
            content["combinations.jsonl"][0]["partition"] = partition
            path = archive_at(source / "availability.tar.gz", content, taken_at=now.isoformat())
            report = inspect_availability(path, policy_from(self.policy))
            if "--snapshot-provider" in arguments:
                self.source_snapshots(source / "snapshots", content, report["sha256"])
            return json.dumps({"archive": str(path), **report})
        if action == "activate-availability":
            if self.fail_activation:
                raise ValueError("consumer refused the new index")
            name = arguments[arguments.index("--index") + 1]
            expected = arguments[arguments.index("--expect-sha256") + 1]
            previous = self.active["indexes"][name]["artifact"]
            if previous["sha256"] != expected:
                raise ValueError("active pin changed")
            published = json.loads(Path(arguments[arguments.index("--publication") + 1]).read_bytes())
            snapshots = {}
            if "--snapshot-publications" in arguments:
                paths = json.loads(Path(arguments[arguments.index("--snapshot-publications") + 1]).read_bytes())
                snapshots = {provider: self.pin(json.loads(Path(path).read_bytes())) for provider, path in paths.items()}
            self.active["indexes"][name] = {"artifact": self.pin(published), "snapshots": snapshots}
            return json.dumps({"activated": True, "index": name, "previous": previous, **self.active["indexes"][name]})
        if action == "export":
            target = Path(arguments[arguments.index("--to") + 1])
            shutil.copyfile(self.catalogue, target)
            from catalogue.archive import inspect_archive
            return json.dumps(inspect_archive(target, config["quality"]))
        raise AssertionError(f"unexpected harvester contract call: {arguments}")

    def execute(self):
        plan = self.configured()
        directory = self.root / "execution"
        directory.mkdir()
        result = run(directory, self.config, plan, self.harvester, prepare_catalogue)
        return directory, result

    def test_complete_run_publishes_verifies_activates_and_documents_exact_bytes(self):
        directory, result = self.execute()
        self.assertTrue(result["complete"])
        self.assertTrue((directory / "complete.json").is_file())
        state, _ = load_state(self.state, self.config)
        publication = json.loads(Path(state["indexes"]["national"]["publication"]).read_bytes())
        self.assertEqual(self.active["indexes"]["national"]["artifact"], self.pin(publication))
        self.assertEqual(state["catalogue"]["archive"], str(self.catalogue))
        self.assertEqual(len((self.hub / "uploads.jsonl").read_text().splitlines()), 2)
        self.assertIn(publication["revision"], (directory / "documentation/README.md").read_text())
        self.assertEqual(len([call for call in self.harvester_calls if call[0] == "availability-status"]), 2)
        self.assertTrue(any(path.endswith("/viewer/national_combinations.jsonl") for path in self.requests))

    def test_changed_consumer_pin_fails_before_collection_or_upload(self):
        original = self.state.read_bytes()
        self.active["indexes"]["national"]["artifact"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "consumer pin differs"):
            self.execute()
        self.assertEqual(self.harvester_calls, [("availability-status",)])
        self.assertEqual(self.state.read_bytes(), original)
        self.assertFalse((self.hub / "uploads.jsonl").exists())
        self.assertFalse(json.loads((self.root / "execution/failure.json").read_bytes())["complete"])

    def test_failed_remote_verification_retains_actual_revision_without_activation(self):
        original = self.state.read_bytes()
        self.corrupt = "availability/availability.tar.gz"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.execute()
        publication = json.loads((self.root / "execution/national-publication/publication.json").read_bytes())
        self.assertFalse(publication["verified"])
        self.assertEqual(len(publication["revision"]), 40)
        self.assertEqual(self.state.read_bytes(), original)
        self.assertFalse(any(call[0] == "activate-availability" for call in self.harvester_calls))

    def test_failed_activation_preserves_state_and_verified_publication(self):
        original = self.state.read_bytes()
        self.fail_activation = True
        with self.assertRaisesRegex(ValueError, "consumer refused"):
            self.execute()
        publication = json.loads((self.root / "execution/national-publication/publication.json").read_bytes())
        self.assertTrue(publication["verified"])
        self.assertEqual(self.state.read_bytes(), original)
        self.assertFalse((self.root / "execution/documentation").exists())

    def test_documentation_failure_preserves_successfully_activated_state(self):
        self.corrupt = "README.md"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.execute()
        state, _ = load_state(self.state, self.config)
        self.assertEqual(state["indexes"]["national"]["activation"], str(self.root / "execution/national-activation/result.json"))
        self.assertTrue(any(call[0] == "activate-availability" for call in self.harvester_calls))
        self.assertFalse((self.root / "execution/complete.json").exists())
        publication = json.loads((self.root / "execution/documentation/publication.json").read_bytes())
        self.assertFalse(publication["verified"])

    def test_licensed_snapshots_are_verified_before_both_consumer_pins_change(self):
        snapshot = {"url": file_url(self.config["hub"], "c" * 40, "source-snapshots/manifest.json"),
                    "revision": "c" * 40, "sha256": "d" * 64, "bytes": 100}
        self.active["indexes"]["national"]["snapshots"] = {"source": snapshot}
        self.activation.write_text(json.dumps({"activated": True, "index": "national", **self.active["indexes"]["national"]}))
        self.plan["indexes"]["national"]["snapshots"] = {
            "providers": ["source"], "shard_prefix_length": 2, "destination": "source-snapshots",
        }
        directory, _ = self.execute()
        publication = json.loads((directory / "national-snapshots/publication.json").read_bytes())
        self.assertTrue(publication["verified"])
        self.assertEqual(self.active["indexes"]["national"]["snapshots"]["source"], self.pin(publication))
        self.assertTrue(any("/source-snapshots/responses/" in path for path in self.requests))
        self.assertEqual(len((self.hub / "uploads.jsonl").read_text().splitlines()), 3)

    def test_discovery_publication_remains_an_explicit_independent_action(self):
        self.plan["discovery"]["action"] = "publish"
        directory, _ = self.execute()
        state, _ = load_state(self.state, self.config)
        self.assertEqual(state["catalogue"]["archive"], str(directory / "discovery/open-data-catalogue.tar.gz"))
        self.assertTrue(any(call[0] == "export" for call in self.harvester_calls))
        self.assertEqual(len((self.hub / "uploads.jsonl").read_text().splitlines()), 3)

    def test_a_retained_index_remains_explicitly_pinned_in_the_card(self):
        state = json.loads(self.state.read_bytes())
        retained = copy.deepcopy(state["indexes"]["national"])
        published = self.initial_publication(self.archive, "availability/retained/availability.tar.gz", "c" * 40)
        retained["publication"], retained["destination"] = published["path"], "availability/retained"
        self.active["indexes"]["retained"] = {"artifact": self.pin(published), "snapshots": {}}
        activation = self.root / "retained-activation.json"
        activation.write_text(json.dumps({"activated": True, "index": "retained", **self.active["indexes"]["retained"]}))
        retained["activation"] = str(activation)
        state["indexes"]["retained"] = retained
        self.state.write_text(json.dumps(state))
        viewer = json.loads(self.viewer.read_bytes())
        for row in copy.deepcopy(viewer["tables"][1:]):
            row.update(name=row["name"].replace("national", "retained"), archive="retained", path=row["path"].replace("national", "retained"))
            viewer["tables"].append(row)
        self.viewer.write_text(json.dumps(viewer))
        directory, _ = self.execute()
        updated = json.loads(self.state.read_bytes())
        self.assertEqual(updated["indexes"]["retained"], retained)
        self.assertIn(published["revision"], (directory / "documentation/README.md").read_text())
        self.assertTrue((directory / "documentation/viewer/retained_combinations.jsonl").is_file())

    def test_freshness_rejects_a_build_too_old_for_the_next_declared_run(self):
        self.source_age = timedelta(hours=23)
        with self.assertRaisesRegex(ValueError, "next declared run budget"):
            self.execute()
        self.assertFalse((self.hub / "uploads.jsonl").exists())

    def test_plan_rejects_weekly_schedule_for_daily_evidence(self):
        self.plan["cadence"]["interval_seconds"] = 604800
        with self.assertRaisesRegex(ValueError, "evidence lifetime"):
            self.configured()

    def test_plan_requires_run_duration_between_source_and_interval_budgets(self):
        for maximum in (5, 3600):
            with self.subTest(maximum=maximum):
                self.plan["cadence"]["maximum_run_seconds"] = maximum
                with self.assertRaisesRegex(ValueError, "run budget"):
                    self.configured()

    def test_plan_requires_confirmed_activation_and_preserves_all_documented_indexes(self):
        activation = json.loads(self.activation.read_bytes())
        activation["activated"] = False
        self.activation.write_text(json.dumps(activation))
        with self.assertRaisesRegex(ValueError, "confirmed matching"):
            self.configured()

    def test_state_lock_and_compare_before_replace_preserve_other_writers(self):
        with state_lock(self.state), self.assertRaisesRegex(RuntimeError, "state lock exists"), state_lock(self.state):
            self.fail("a concurrent state writer entered")
        original = self.state.read_bytes()
        self.state.write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed concurrently"):
            write_json(self.state, {}, expected=original)
        self.assertEqual(self.state.read_text(), "changed")

    def test_schedule_uses_validated_interval_and_exact_plan_without_installing(self):
        self.configured()
        settings = self.config["schedule"]
        for key in ("weekday", "hour", "minute"):
            del settings[key]
        settings.update(action="run-update", plan=self.plan_path, interval_seconds=3600, log=self.root / "schedule.log")
        output = self.root / "job.plist"
        schedule(self.root / "publisher.toml", self.config, output)
        payload = plistlib.loads(output.read_bytes())
        self.assertEqual(payload["StartInterval"], 3600)
        self.assertNotIn("StartCalendarInterval", payload)
        self.assertEqual(payload["ProgramArguments"][-3:], ["run-update", "--plan", str(self.plan_path)])
        settings["interval_seconds"] = 604800
        with self.assertRaisesRegex(ValueError, "must match"):
            schedule(self.root / "publisher.toml", self.config, self.root / "invalid.plist")

    def test_runtime_deadline_is_explicit_and_never_extends_a_request_timeout(self):
        self.assertEqual(remaining({}, 12), 12)
        self.assertLess(remaining({"run_deadline": time.monotonic() + 1}, 12), 1)
        with self.assertRaisesRegex(TimeoutError, "maximum run"):
            remaining({"run_deadline": time.monotonic() - 1})

    def test_schedule_configuration_requires_plan_interval_instead_of_calendar_fields(self):
        self.configured()
        template = (ROOT / "publisher.example.toml").read_text()
        template = template.replace('action = "prepare"', 'action = "run-update"\nplan = ' + json.dumps(str(self.plan_path)) + '\ninterval_seconds = 3600')
        target = self.root / "publisher.toml"
        target.write_text(template)
        with self.assertRaisesRegex(ValueError, "exactly"):
            load_config(target)
        for field in ("weekday = 1\n", "hour = 3\n", "minute = 0\n"):
            template = template.replace(field, "")
        target.write_text(template)
        config = load_config(target)
        self.assertEqual(config["schedule"]["plan"], self.plan_path)
        self.assertEqual(config["schedule"]["interval_seconds"], 3600)

    def test_cli_refuses_invalid_update_state_before_any_harvester_execution(self):
        self.plan["cadence"]["interval_seconds"] = 604800
        self.plan_path.write_text(json.dumps(self.plan))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "update"), "--config", str(ROOT / "publisher.example.toml"),
             "run-update", "--plan", str(self.plan_path)], text=True, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("configured repository", completed.stderr)
        self.assertFalse((self.hub / "uploads.jsonl").exists())

    def test_expired_evidence_cannot_be_renewed_by_publication(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            require_fresh(self.archive, now=datetime(2026, 9, 10, tzinfo=UTC), required_until=datetime(2026, 9, 11, tzinfo=UTC))

    def source_snapshots(self, directory, content, digest):
        (directory / "responses").mkdir(parents=True)
        source = content["partitions.jsonl"][0]["receipts"][0]
        body = json.dumps({"schema_version": 1, "responses": {source["sha256"]: {
            "schema_version": 1, "provider": "source", "source": source, "payload": {"observations": [10]},
        }}}).encode()
        asset = hashlib.sha256(body).hexdigest()
        (directory / f"responses/{asset}.json").write_bytes(body)
        (directory / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "availability_sha256": digest,
            "providers": {"source": {"observations": "c" * 64}},
            "responses": {source["sha256"]: {"sha256": asset, "bytes": len(body)}},
            "projections": {"source": {"identity_fields": [], "datasets": {"observations": {
                "licence": "CC BY 4.0", "attribution": "Source", "source_url": "https://example.org/observations", "fields": ["observations"],
            }}}},
        }))
