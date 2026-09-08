"""Hub documentation verifies published bytes and exposes rejected catalogue gates."""

import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path

from test_availability import archive_at, tables
from test_release import rows, write_archive

from catalogue.config import load
from catalogue.documentation import prepare
from catalogue.viewer import load as load_viewer
from catalogue.viewer import project

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalogue = self.root / "catalogue.tar.gz"
        data = rows()
        data["opendata_structures"][0]["error"] = "source request failed"
        write_archive(self.catalogue, data)
        self.availability = archive_at(self.root / "availability.tar.gz", tables())
        self.policy = self.root / "availability-policy.toml"
        self.policy.write_text((ROOT / "availability-policy.example.toml").read_text().replace(
            'providers = ["dvns", "cruscotto"]', 'providers = ["source"]',
        ))
        self.config = load(ROOT / "publisher.example.toml")
        self.config["quality"].update(minimum_datasets=1, providers={"sample": {"languages": ["en"], "vocabulary": True}})
        self.payloads = {"open-data-catalogue.tar.gz": self.catalogue.read_bytes(), "availability.tar.gz": self.availability.read_bytes()}
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                payload = owner.payloads[self.path.rsplit("/", 1)[1]]
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
        self.config["hub"]["endpoint"] = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def prepare(self):
        directory = self.root / "publication"
        directory.mkdir()
        prepare(directory, self.config, self.catalogue, "a" * 40, self.availability, "b" * 40,
                self.policy, ROOT / "README.hub.md", ROOT / "viewer.json")
        return directory

    def test_failed_catalogue_policy_remains_visible_beside_independent_availability(self):
        directory = self.prepare()
        report = json.loads((directory / "catalogue-quality.json").read_bytes())
        self.assertFalse(report["accepted"])
        self.assertEqual(report["report"]["metrics"]["structure_errors"], 1)
        text = (directory / "README.md").read_text()
        self.assertIn("**does not pass**", text)
        self.assertIn("across 1 datasets", text)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual({path.name for path in directory.iterdir()}, {"README.md", "catalogue-quality.json", "viewer-manifest.json", "viewer"})

    def test_different_remote_bytes_prevent_a_new_card(self):
        self.payloads["availability.tar.gz"] = b"different"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.prepare()
        self.assertFalse((self.root / "publication/README.md").exists())

    def test_viewer_selects_only_typed_tables_and_preserves_source_rows(self):
        directory = self.prepare()
        text = (directory / "README.md").read_text()
        configs = json.loads(next(line.removeprefix("configs: ") for line in text.splitlines() if line.startswith("configs: ")))
        manifest = json.loads((directory / "viewer-manifest.json").read_bytes())
        self.assertEqual(len(configs), 3)
        self.assertEqual(sum(config["default"] for config in configs), 1)
        self.assertEqual({config["data_files"][0]["path"] for config in configs}, {row["path"] for row in manifest["files"]})
        for config in configs:
            self.assertEqual(config["data_files"][0]["split"], "data")
            row = json.loads((directory / config["data_files"][0]["path"]).read_text())
            self.assertEqual(set(row), {feature["name"] for feature in config["features"]})
        catalogue = json.loads((directory / "viewer/catalogue.jsonl").read_text())
        self.assertEqual(json.loads(catalogue["record_json"]), rows()["opendata_catalog"][0])
        combination = json.loads((directory / "viewer/availability_combinations.jsonl").read_text())
        original = tables()["combinations.jsonl"][0]
        self.assertEqual(json.loads(combination["dimensions_json"]), original["dimensions"])
        self.assertEqual(combination["territory_code"], original["territory"]["code"])

    def test_viewer_preserves_nulls_and_rejects_missing_or_mistyped_fields(self):
        columns = load_viewer(ROOT / "viewer.json")[0]["columns"]
        row = rows()["opendata_catalog"][0]
        row["served"], row["licence"] = None, None
        self.assertIsNone(project(row, columns)["served"])
        self.assertIsNone(project(row, columns)["licence"])
        row["served"] = "unknown"
        with self.assertRaisesRegex(ValueError, "wrong type"):
            project(row, columns)
        del row["served"]
        with self.assertRaisesRegex(ValueError, "missing"):
            project(row, columns)

    def test_viewer_rejects_path_traversal_before_writing(self):
        config = json.loads((ROOT / "viewer.json").read_text())
        config["tables"][0]["path"] = "../escape.jsonl"
        path = self.root / "viewer.json"
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "canonical relative"):
            load_viewer(path)
