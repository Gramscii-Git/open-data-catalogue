"""Explicit unit protocol receipts exercise verified provider groups without Hub writes."""

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_release import DOCUMENT_CONTRACT, digest, rows, write_archive

from catalogue.archive import inspect_archive
from catalogue.config import load as load_publisher
from catalogue.publish import file_url
from catalogue.viewer import load, prepare, project, published, update_card

ROOT = Path(__file__).resolve().parents[1]


class ViewerGroups(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "viewer.json"
        self.config = json.loads((ROOT / "viewer.json").read_text())
        self.config["published"] = []
        self.config["groups"] = [{"name": "planning", "providers": ["second", "first"]}]
        self.columns = load(ROOT / "viewer.json")[0]["columns"]
        self.hub = {"endpoint": "https://hub.example.test", "repository": "owner/catalogue", "timeout_seconds": 7}
        self.payloads = {}
        for provider in ("first", "second", "statistics"):
            source = rows()["opendata_catalog"][0]
            source["provider"] = provider
            self.add_provider(provider, [project(source, self.columns)])
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.config))

    def add_provider(self, provider, values, *, config_name=None):
        data = ("\n".join(json.dumps(value) for value in values) + "\n").encode()
        receipt = {
            "schema_version": 1, "config_name": config_name or provider,
            "rows": len(values), "path": "catalogue.jsonl",
            "sha256": hashlib.sha256(data).hexdigest(), "source_sha256": "a" * 64,
        }
        content = json.dumps(receipt).encode()
        entry = {
            "provider": provider, "destination": f"providers/{provider}", "revision": "b" * 40,
            "viewer_sha256": hashlib.sha256(content).hexdigest(), "viewer_bytes": len(content),
            "data_bytes": len(data),
        }
        self.config["published"] = [value for value in self.config["published"] if value["provider"] != provider]
        self.config["published"].append(entry)
        for path, payload in ((f"providers/{provider}/viewer.json", content),
                              (f"providers/{provider}/catalogue.jsonl", data)):
            self.payloads[file_url(self.hub, entry["revision"], path)] = payload

    def response(self, url, *, timeout):
        self.assertEqual(timeout, self.hub["timeout_seconds"])
        response = io.BytesIO(self.payloads[url])
        response.status = 200
        return response

    def read(self):
        self.save()
        with patch("catalogue.viewer.urllib.request.urlopen", side_effect=self.response) as requests:
            metadata, evidence = published(self.path, self.hub)
        self.assertEqual(requests.call_count, 2 * len(self.config["published"]))
        return metadata, evidence

    def test_group_uses_only_declared_providers_in_declared_order(self):
        metadata, evidence = self.read()
        group = metadata[-1]
        self.assertEqual(group["config_name"], "planning")
        self.assertFalse(group["default"])
        self.assertEqual(group["data_files"], [{"split": "data", "path": [
            "providers/second/catalogue.jsonl", "providers/first/catalogue.jsonl",
        ]}])
        self.assertEqual(group["features"], metadata[0]["features"])
        self.assertEqual({entry["provider"] for entry in evidence}, {"first", "second", "statistics"})
        card = update_card("---\nconfigs: []\n---\n", metadata)
        self.assertEqual(json.loads(card.splitlines()[1].removeprefix("configs: ")), metadata)

    def test_release_builder_preserves_verified_group_paths_and_receipts(self):
        external = self.read()
        archive = self.path.parent / "catalogue.tar.gz"
        write_archive(archive, rows())
        policy = load_publisher(ROOT / "publisher.example.toml")["quality"]
        policy.update(minimum_datasets=1, providers={"sample": {"languages": ["en"], "vocabulary": True}},
                      document_contract_sha256=digest(DOCUMENT_CONTRACT))
        report = inspect_archive(archive, policy)
        tables = [table for table in load(self.path) if table["name"] == "catalogue"]
        card = prepare(self.path.parent, tables, {"catalogue": archive}, {"catalogue": report}, external)
        metadata = json.loads(card.removeprefix("configs: "))
        self.assertEqual(metadata[1:], external[0])
        self.assertEqual(sum(entry["default"] for entry in metadata), 1)
        manifest = json.loads((self.path.parent / "viewer-manifest.json").read_text())
        self.assertEqual(manifest["published_files"], external[1])
        self.assertEqual(manifest["files"][0]["source_sha256"], report["sha256"])
        output = self.path.parent / "viewer/catalogue.jsonl"
        self.assertEqual(json.loads(output.read_text()), project(rows()["opendata_catalog"][0], self.columns))

    def test_group_schema_refuses_incomplete_or_undeclared_members_before_http(self):
        invalid = [[], ["first", "first"], ["missing"], [None], "first"]
        for providers in invalid:
            with self.subTest(providers=providers):
                self.config["groups"] = [{"name": "planning", "providers": providers}]
                self.save()
                with patch("catalogue.viewer.urllib.request.urlopen") as requests:
                    with self.assertRaisesRegex(ValueError, "unique explicitly published"):
                        published(self.path, self.hub)
                    requests.assert_not_called()

    def test_group_names_refuse_collisions_and_unknown_fields(self):
        for groups in ([{"name": "catalogue", "providers": ["first"]}],
                       [{"name": "planning-bad", "providers": ["first"]}],
                       [{"name": "planning", "providers": ["first"], "extra": True}],
                       [self.config["groups"][0], self.config["groups"][0]]):
            with self.subTest(groups=groups):
                self.config["groups"] = groups
                self.save()
                with self.assertRaises(ValueError):
                    load(self.path)

    def test_duplicate_provider_receipts_are_refused(self):
        self.config["published"].append(self.config["published"][0])
        self.save()
        with self.assertRaisesRegex(ValueError, "providers must be unique"):
            load(self.path)

    def test_missing_groups_and_obsolete_schema_are_explicit_errors(self):
        original = copy.deepcopy(self.config)
        for change in ("missing", "obsolete", "wrong_type"):
            self.config = copy.deepcopy(original)
            if change == "missing":
                del self.config["groups"]
            elif change == "obsolete":
                self.config["schema_version"] = 3
            else:
                self.config["groups"] = None
            self.save()
            with self.assertRaises((ValueError, TypeError)):
                load(self.path)

    def test_group_name_cannot_be_a_provider_config_name(self):
        source = rows()["opendata_catalog"][0]
        source["provider"] = "first"
        self.add_provider("first", [project(source, self.columns)], config_name="planning")
        self.save()
        with (patch("catalogue.viewer.urllib.request.urlopen", side_effect=self.response),
              self.assertRaisesRegex(ValueError, "names and paths must be unique")):
            published(self.path, self.hub)

    def test_wrong_provider_duplicate_dataset_and_mistyped_projection_are_refused(self):
        source = rows()["opendata_catalog"][0]
        source["provider"] = "first"
        row = project(source, self.columns)
        cases = [[project(rows()["opendata_catalog"][0], self.columns)], [row, row],
                 [{**row, "active": 1}], [{**row, "title": "invented"}],
                 [{**row, "unknown": True}], [{**row, "record_json": "null"}]]
        for values in cases:
            with self.subTest(values=values):
                self.add_provider("first", values)
                self.save()
                with (patch("catalogue.viewer.urllib.request.urlopen", side_effect=self.response),
                      self.assertRaises(ValueError)):
                    published(self.path, self.hub)

    def test_corrupt_data_fails_hash_readback_before_group_creation(self):
        url = file_url(self.hub, "b" * 40, "providers/first/catalogue.jsonl")
        self.payloads[url] = self.payloads[url].replace(b"first", b"wrong")
        with (patch("catalogue.viewer.urllib.request.urlopen", side_effect=self.response),
              self.assertRaisesRegex(RuntimeError, "size and SHA-256")):
            published(self.path, self.hub)

    def test_card_updates_group_paths_and_keeps_compatible_provider_views(self):
        metadata, _ = self.read()
        held = {**metadata[0], "config_name": "held"}
        card = "configs: " + json.dumps([held]) + "\n"
        updated = update_card(card, metadata)
        self.assertEqual(len(json.loads(updated.removeprefix("configs: "))), 5)
        self.assertEqual(update_card(updated, metadata), updated)

    def test_card_refuses_incompatible_features_on_shared_group_paths(self):
        metadata, _ = self.read()
        held = {**metadata[-1], "config_name": "held", "features": []}
        card = "configs: " + json.dumps([held]) + "\n"
        with self.assertRaisesRegex(ValueError, "identical features"):
            update_card(card, metadata)
