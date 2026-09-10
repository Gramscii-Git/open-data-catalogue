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
from catalogue.documentation_releases import load as load_releases
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
        self.releases = self.root / "releases.json"
        releases = json.loads((ROOT / "documentation-releases.example.json").read_text())
        self.payloads = {"open-data-catalogue.tar.gz": self.catalogue.read_bytes()}
        for name, release in releases["indexes"].items():
            content = tables()
            for values in content.values():
                for row in values:
                    row["dataset_id"] = name
            if name != "national":
                content["combinations.jsonl"][0]["territory"] = None
            path = self.availability if name == "national" else self.root / f"{name}.tar.gz"
            if name != "national":
                archive_at(path, content)
            release.update(archive=path.name, policy=self.policy.name, revision="b" * 40)
            self.payloads[f"{release['destination']}/availability.tar.gz"] = path.read_bytes()
        self.releases.write_text(json.dumps(releases))
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                payload = owner.payloads[self.path.split("/resolve/", 1)[1].split("/", 1)[1]]
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
        prepare(directory, self.config, self.catalogue, "a" * 40, self.releases,
                ROOT / "README.hub.md", ROOT / "viewer.json")
        return directory

    def test_failed_catalogue_policy_remains_visible_beside_independent_availability(self):
        directory = self.prepare()
        report = json.loads((directory / "catalogue-quality.json").read_bytes())
        self.assertFalse(report["accepted"])
        self.assertEqual(report["report"]["metrics"]["structure_errors"], 1)
        text = (directory / "README.md").read_text()
        self.assertIn("**does not pass**", text)
        self.assertIn("across 3 datasets", text)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual({path.name for path in directory.iterdir()}, {"README.md", "catalogue-quality.json", "viewer-manifest.json", "viewer"})

    def test_different_remote_bytes_prevent_a_new_card(self):
        self.payloads["availability/eurostat-series/availability.tar.gz"] = b"different"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.prepare()
        self.assertFalse((self.root / "publication/README.md").exists())

    def test_source_labels_publish_without_invented_calendar_bounds(self):
        content = tables()
        content["datasets.jsonl"][0]["period_kind"] = "source-label"
        period = {"id": "2026/27", "label": "School year 2026/27", "start": None, "end": None}
        content["combinations.jsonl"][0]["period"] = period
        archive_at(self.availability, content)
        self.payloads["availability/availability.tar.gz"] = self.availability.read_bytes()
        directory = self.prepare()
        row = json.loads((directory / "viewer/national_combinations.jsonl").read_text())
        self.assertEqual(row["period"], period["id"])
        self.assertIsNone(row["period_start"])
        self.assertIsNone(row["period_end"])

    def test_viewer_selects_only_typed_tables_and_preserves_source_rows(self):
        directory = self.prepare()
        text = (directory / "README.md").read_text()
        configs = json.loads(next(line.removeprefix("configs: ") for line in text.splitlines() if line.startswith("configs: ")))
        manifest = json.loads((directory / "viewer-manifest.json").read_bytes())
        self.assertEqual(len(configs), 7)
        self.assertEqual(sum(config["default"] for config in configs), 1)
        self.assertEqual({config["data_files"][0]["path"] for config in configs}, {row["path"] for row in manifest["files"]})
        for config in configs:
            self.assertEqual(config["data_files"][0]["split"], "data")
            row = json.loads((directory / config["data_files"][0]["path"]).read_text())
            self.assertEqual(set(row), {feature["name"] for feature in config["features"]})
        catalogue = json.loads((directory / "viewer/catalogue.jsonl").read_text())
        self.assertEqual(json.loads(catalogue["record_json"]), rows()["opendata_catalog"][0])
        combination = json.loads((directory / "viewer/national_combinations.jsonl").read_text())
        original = tables()["combinations.jsonl"][0]
        self.assertEqual(json.loads(combination["dimensions_json"]), original["dimensions"])
        self.assertEqual(combination["territory_code"], original["territory"]["code"])
        for name in ("ssn_history", "eurostat_series"):
            row = json.loads((directory / f"viewer/{name}_combinations.jsonl").read_text())
            self.assertIsNone(row["territory_code"])
            self.assertIsNone(row["territory_label"])
            self.assertIsNone(row["territory_level"])
        self.assertEqual({row["source_archive"] for row in manifest["files"]},
                         {"catalogue", "national", "ssn-history", "eurostat-series"})

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

    def test_viewer_requires_every_published_index(self):
        releases = json.loads(self.releases.read_text())
        del releases["indexes"]["ssn-history"]
        self.releases.write_text(json.dumps(releases))
        with self.assertRaisesRegex(ValueError, "exactly the declared archive set"):
            self.prepare()
        self.assertFalse((self.root / "publication/README.md").exists())

    def test_missing_geography_is_rejected_while_explicit_null_is_retained(self):
        columns = load_viewer(ROOT / "viewer.json")[2]["columns"]
        row = tables()["combinations.jsonl"][0]
        row["territory"] = None
        self.assertIsNone(project(row, columns)["territory_code"])
        del row["territory"]
        with self.assertRaisesRegex(ValueError, "missing"):
            project(row, columns)

    def test_releases_reject_unpinned_revisions_duplicate_destinations_and_unknown_fields(self):
        original = json.loads(self.releases.read_text())
        for key, value, message in (
            ("revision", "main", "immutable full commit"),
            ("destination", "../escape", "canonical relative"),
            ("destination", "availability/ssn-history", "distinct"),
            ("extra", True, "incomplete or unknown"),
        ):
            with self.subTest(key=key, value=value):
                config = json.loads(json.dumps(original))
                config["indexes"]["national"][key] = value
                self.releases.write_text(json.dumps(config))
                with self.assertRaisesRegex(ValueError, message):
                    load_releases(self.releases)
