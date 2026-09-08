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
                self.policy, ROOT / "README.hub.md")
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
        self.assertEqual({path.name for path in directory.iterdir()}, {"README.md", "catalogue-quality.json"})

    def test_different_remote_bytes_prevent_a_new_card(self):
        self.payloads["availability.tar.gz"] = b"different"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.prepare()
        self.assertFalse((self.root / "publication/README.md").exists())
