"""Declared child configuration is independent of the invoking shell."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalogue.cli import harvester
from catalogue.config import load, process_environment

ROOT = Path(__file__).resolve().parents[1]


class HarvesterEnvironmentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        package = self.root / "core/server/sdg/plugins/opendata"
        package.mkdir(parents=True)
        (package / "__main__.py").write_bytes((ROOT / "tests/fixtures/harvester_environment.py").read_bytes())
        environment = self.root / "deployment.env"
        environment.write_text('DATABASE_URL="declared database"\nOPENDATA_PACING="declared pacing"\n')
        self.config = {"deployment": {"harvester": self.root / "core", "python": Path(sys.executable),
                                      "environment_file": environment, "stop_grace_seconds": 2,
                                      "process_environment": {"NATIVE_CONTEXT": "declared context"}}}

    def test_hostile_parent_settings_do_not_reach_the_native_child(self):
        hostile = {"DATABASE_URL": "wrong database", "OPENDATA_PACING": "wrong pacing",
                   "HTTP_HOSTS": "wrong hosts", "AUTH_TOKEN": "parent secret",
                   "PYTHONPATH": "wrong modules", "UNDECLARED_PARENT": "wrong context"}
        with patch.dict(os.environ, hostile):
            observed = json.loads(harvester(self.config, capture=True))
        for key in hostile.keys() - {"PYTHONPATH"}:
            self.assertNotIn(key, observed["environment_keys"])
        self.assertEqual(observed["environment"]["NATIVE_CONTEXT"], "declared context")
        self.assertEqual(observed["environment"]["PYTHONPATH"], str(self.root / "core/server"))
        self.assertEqual(observed["environment_file"], str(self.config["deployment"]["environment_file"]))
        self.assertEqual(observed["file_content"], self.config["deployment"]["environment_file"].read_text())
        self.assertEqual(observed["prefix"], sys.prefix)

    def test_a_declared_process_setting_is_passed_exactly(self):
        self.config["deployment"]["process_environment"]["DATABASE_URL"] = "explicit process override"
        with patch.dict(os.environ, {"DATABASE_URL": "unrelated parent"}):
            observed = json.loads(harvester(self.config, capture=True))
        self.assertEqual(observed["environment"]["DATABASE_URL"], "explicit process override")
        self.assertIn('DATABASE_URL="declared database"', observed["file_content"])

    def test_process_environment_is_required_by_the_configuration_schema(self):
        template = (ROOT / "publisher.example.toml").read_text()
        path = self.root / "publisher.toml"
        path.write_text("\n".join(line for line in template.splitlines() if not line.startswith("process_environment =")))
        with self.assertRaisesRegex(ValueError, "process_environment"):
            load(path)

    def test_process_environment_rejects_ambiguous_values_and_import_overrides(self):
        for value in (None, [], {"A": 1}, {"A": True}, {"A": "a\0b"}, {"A=B": "x"},
                      {"": "x"}, {"PYTHONPATH": "unrelated source"}):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                process_environment(value)
        self.assertEqual(process_environment({"__CF_USER_TEXT_ENCODING": "explicit", "EMPTY": ""}),
                         {"__CF_USER_TEXT_ENCODING": "explicit", "EMPTY": ""})
        self.assertEqual(process_environment({}), {})
