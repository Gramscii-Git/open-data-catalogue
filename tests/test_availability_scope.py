"""Complete inventory expansion against a native, isolated HTTPS source."""

import copy
import hashlib
import http.server
import json
import os
import ssl
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from catalogue.availability_build import captured_scope
from catalogue.availability_scope import resolve, verify_inventory_scope

TLS = Path(__file__).parent / "fixtures/tls"


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.rows = [{"code": "000001"}, {"code": "000002"}]
        self.status = 200
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.calls.append(self.path)
                body = json.dumps(owner.rows).encode()
                self.send_response(owner.status)
                self.send_header("Location", "/redirected")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(TLS / "localhost.cert.pem", TLS / "localhost.key.pem")
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.close)
        self.environment = patch.dict(os.environ, {"SSL_CERT_FILE": str(TLS / "localhost.cert.pem")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.spec = {
            "schema_version": 3, "limits": json.loads((Path(__file__).resolve().parents[1] / "scopes/dvns-cofog.json").read_bytes())["limits"],
            "inventories": {"municipalities": {
                "url": f"https://127.0.0.1:{self.server.server_port}/inventory.json",
                "code_field": "code", "code_pattern": "[0-9]{6}",
                "max_bytes": 4096, "max_records": 10, "timeout_seconds": 2,
            }},
            "datasets": [{"provider": "source", "dataset_id": name,
                          "varying": {"istat_code": {"inventory": "municipalities"}}}
                         for name in ("population", "schools")],
        }

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_each_inventory_is_read_once_for_all_domains(self):
        original = copy.deepcopy(self.spec)
        resolved, evidence = resolve(self.spec)
        self.assertEqual(self.spec, original)
        self.assertEqual(self.calls, ["/inventory.json"])
        self.assertEqual(resolved["schema_version"], 2)
        self.assertEqual(len(evidence["bindings"]), 2)
        for dataset in resolved["datasets"]:
            self.assertEqual(dataset["varying"]["istat_code"], ["000001", "000002"])
        self.assertEqual(evidence["inventories"]["municipalities"]["receipt"]["status"], 200)

    def test_obsolete_scope_and_deadlines_fail_before_inventory_requests(self):
        original = copy.deepcopy(self.spec)
        self.spec["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema version 3"):
            resolve(self.spec)
        for field in ("request_timeout_seconds", "operation_timeout_seconds"):
            self.spec = copy.deepcopy(original)
            self.spec["limits"][field] = 10
            with self.assertRaisesRegex(ValueError, "scope limits must contain exactly"):
                resolve(self.spec)
        self.assertEqual(self.calls, [])

    def test_invalid_and_duplicate_codes_cannot_be_omitted(self):
        for rows in ([], [{"code": 1}], [{"code": "1"}], [{"code": "000001"}] * 2):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(ValueError):
                    resolve(self.spec)

    def test_redirect_does_not_switch_the_inventory_source(self):
        self.status = 302
        with self.assertRaisesRegex(ValueError, "redirected"):
            resolve(self.spec)
        self.assertEqual(self.calls, ["/inventory.json"])

    def test_a_subset_cannot_be_published_as_the_full_inventory(self):
        resolved, evidence = resolve(self.spec)
        resolved["datasets"][0]["varying"]["istat_code"] = ["000001"]
        with self.assertRaisesRegex(ValueError, "complete source inventory"):
            verify_inventory_scope(resolved, evidence)

    def test_pinned_inventory_reconstruction_performs_no_new_source_read(self):
        resolved, evidence = resolve(self.spec)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            scope, receipt = directory / "scope.json", directory / "inventory.json"
            scope.write_text(json.dumps(resolved))
            receipt.write_text(json.dumps(evidence))
            digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            self.calls.clear()
            self.assertEqual(captured_scope(scope, receipt, digest), (resolved, evidence))
            self.assertEqual(self.calls, [])
            with self.assertRaisesRegex(ValueError, "digest pin"):
                captured_scope(scope, receipt, "0" * 64)
            resolved["datasets"][0]["varying"]["istat_code"].pop()
            scope.write_text(json.dumps(resolved))
            with self.assertRaisesRegex(ValueError, "complete source inventory"):
                captured_scope(scope, receipt, digest)
            self.assertEqual(self.calls, [])

    def test_resource_limits_are_enforced(self):
        for name in ("max_bytes", "max_records"):
            with self.subTest(limit=name):
                specification = copy.deepcopy(self.spec)
                specification["inventories"]["municipalities"][name] = 1
                with self.assertRaises(ValueError):
                    resolve(specification)

    def test_missing_configuration_is_refused_before_source_access(self):
        del self.spec["inventories"]["municipalities"]["code_pattern"]
        with self.assertRaises(ValueError):
            resolve(self.spec)
        self.assertEqual(self.calls, [])

    def test_inventory_provenance_cannot_be_detached_or_changed(self):
        resolved, evidence = resolve(self.spec)
        for changes in ({"status": 503}, {"bytes": 0}, {"sha256": "unknown"},
                        {"url": "https://example.org/different"}, {"observed_at": "2026-09-09T00:00:00"}):
            with self.subTest(changes=changes):
                altered = copy.deepcopy(evidence)
                altered["inventories"]["municipalities"]["receipt"].update(changes)
                with self.assertRaises(ValueError):
                    verify_inventory_scope(resolved, altered)
        evidence["bindings"] = []
        with self.assertRaisesRegex(ValueError, "must bind"):
            verify_inventory_scope(resolved, evidence)

    def test_a_binding_must_identify_a_real_scope_argument(self):
        resolved, evidence = resolve(self.spec)
        evidence["bindings"][0]["argument"] = "unknown"
        with self.assertRaisesRegex(ValueError, "declared request argument"):
            verify_inventory_scope(resolved, evidence)
