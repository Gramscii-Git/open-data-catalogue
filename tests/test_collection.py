"""Collection checkpoints bind real child commands, source revisions and locks."""

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from catalogue.collection import load, read_state, run
from catalogue.runtime import process_lock

ROOT = Path(__file__).resolve().parents[1]


class CollectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.core = self.root / "core"
        package = self.core / "server/sdg/plugins/opendata"
        package.mkdir(parents=True)
        (package / "__main__.py").write_bytes((ROOT / "tests/fixtures/collection_command.py").read_bytes())
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Collection Test", "-c", "user.email=collection@example.invalid",
                 "commit", "--no-gpg-sign", "-qm", "Declare command fixture")
        self.environment = self.root / "deployment.env"
        self.calls = self.root / "calls.jsonl"
        self.failure = self.root / "fail-structure"
        self.environment.write_text(json.dumps({"calls": str(self.calls), "failure": str(self.failure)}))
        self.policy = self.root / "retry.json"
        self.policy.write_text(json.dumps({"contract": "validated by the native child"}))
        self.publisher = self.root / "publisher.toml"
        template = (ROOT / "publisher.example.toml").read_text()
        replacements = {
            'harvester = "../semantic-deterministic-graph"': f'harvester = {json.dumps(str(self.core))}',
            'environment_file = "../semantic-deterministic-graph/server/.env"': f'environment_file = {json.dumps(str(self.environment))}',
            'python = "../semantic-deterministic-graph/server/.venv/bin/python"': f'python = {json.dumps(sys.executable)}',
        }
        for original, replacement in replacements.items():
            template = template.replace(original, replacement)
        self.publisher.write_text(template)
        self.plan_path = self.root / "collection.json"
        self.plan = {"schema": 1,
                     "publisher": {"path": str(self.publisher), "sha256": self.digest(self.publisher)},
                     "retry_policy": {"path": str(self.policy), "sha256": self.digest(self.policy)},
                     "environment_sha256": self.digest(self.environment),
                     "harvester_revision": self.git("rev-parse", "HEAD"),
                     "provider": "istat", "steps": ["sync", "structure"],
                     "directory": str(self.root / "collection"), "wait_for_current": True,
                     "notification": {"complete": None, "failed": None}}
        self.save_plan()

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.core), *arguments], text=True).strip()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def save_plan(self):
        self.plan_path.write_text(json.dumps(self.plan))

    def execute(self, **options):
        with contextlib.redirect_stdout(io.StringIO()):
            run(self.plan_path, **options)

    def state(self):
        return json.loads((self.root / "collection/state.json").read_text())

    def steps(self):
        return [json.loads(line)["step"] for line in self.calls.read_text().splitlines()]

    def test_completed_phases_survive_failure_and_are_not_reexecuted(self):
        self.failure.touch()
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        self.assertEqual(self.state()["completed"], ["sync"])
        self.assertEqual(self.state()["status"], "failed")
        self.assertEqual(self.state()["error"]["returncode"], 7)
        self.failure.unlink()
        self.execute()
        self.execute()
        self.assertEqual(self.steps(), ["sync", "structure", "structure"])
        self.assertEqual(self.state()["status"], "complete")

    def test_input_changes_cannot_reuse_completed_phases(self):
        self.execute()
        self.plan["provider"] = "changed-provider"
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "different inputs"):
            self.execute()
        self.assertEqual(self.steps(), ["sync", "structure"])

    def test_check_does_not_start_collection_or_write_state(self):
        self.execute(check=True)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / "collection").exists())

    def test_mutable_or_different_source_is_rejected_before_collection(self):
        (self.core / "untracked.py").write_text("raise RuntimeError('not admitted')\n")
        with self.assertRaisesRegex(ValueError, "clean harvester"):
            self.execute()
        self.assertFalse(self.calls.exists())
        (self.core / "untracked.py").unlink()
        self.plan["harvester_revision"] = "0" * 40
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "revision differs"):
            self.execute()

    def test_changed_environment_or_policy_is_rejected(self):
        for path in (self.environment, self.policy):
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "declared digest"):
                load(self.plan_path)
            path.write_bytes(original)

    def test_invalid_phase_order_unknown_fields_and_forged_completion_are_rejected(self):
        for key, value in (("steps", ["structure", "sync"]), ("steps", ["sync", "sync"]),
                           ("wait_for_current", "yes"), ("extra", True)):
            original = dict(self.plan)
            self.plan[key] = value
            self.save_plan()
            with self.assertRaises(ValueError):
                load(self.plan_path)
            self.plan = original
        self.save_plan()
        self.execute()
        path = self.root / "collection/state.json"
        state = self.state()
        state["completed"] = ["sync"]
        path.write_text(json.dumps(state))
        plan, _, binding = load(self.plan_path)
        with self.assertRaisesRegex(ValueError, "pending steps"):
            read_state(path, plan, binding)
        state["schema"] = True
        state["completed"] = self.plan["steps"]
        path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "different inputs"):
            read_state(path, plan, binding)

    def test_notification_failure_does_not_repeat_successful_collection(self):
        marker = self.root / "notification-fails"
        marker.touch()
        script = self.root / "notify.py"
        script.write_text("import pathlib,sys\nraise SystemExit(9 if pathlib.Path(sys.argv[1]).exists() else 0)\n")
        self.plan["notification"]["complete"] = [sys.executable, str(script), str(marker)]
        self.save_plan()
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        self.assertEqual(self.state()["status"], "complete")
        self.assertEqual(self.state()["notification"], "failed")
        marker.unlink()
        self.execute()
        self.assertEqual(self.steps(), ["sync", "structure"])
        self.assertEqual(self.state()["notification"], "sent")

    def test_waiting_collector_starts_only_after_the_existing_publisher_releases(self):
        build = self.root / "build"
        build.mkdir()
        with process_lock(build / ".publisher.lock", label="publisher"):
            child = subprocess.Popen([sys.executable, str(ROOT / "collect"), "--plan", str(self.plan_path)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env={**os.environ, "PYTHONPATH": str(ROOT)})
            self.addCleanup(self.reap, child)
            deadline = time.monotonic() + 5
            while not (self.root / "collection/state.json").exists():
                if child.poll() is not None or time.monotonic() >= deadline:
                    self.fail("collector does not enter its declared wait")
                time.sleep(0.01)
            self.assertEqual(self.state()["status"], "waiting")
            self.assertFalse(self.calls.exists())
            self.assertIsNone(child.poll())
            with self.assertRaisesRegex(RuntimeError, "collection lock"):
                self.execute()
        _, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stderr.decode())
        self.assertEqual(self.steps(), ["sync", "structure"])

    @staticmethod
    def reap(child):
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
