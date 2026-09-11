"""Real command and HTTP lifetimes remain independent of elapsed work time."""

import hashlib
import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from catalogue.cli import publication_lock
from catalogue.config import load
from catalogue.publish import verify_download
from catalogue.runtime import run_command

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tests/fixtures/owned_command.py"


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = {**os.environ, "PYTHONPATH": str(ROOT)}

    def test_progressing_command_outlives_shutdown_grace_and_preserves_output(self):
        source = "import sys,time; data=sys.stdin.read(); time.sleep(0.25); print(data); print('detail',file=sys.stderr)"
        result = run_command([sys.executable, "-c", source], stop_grace=0.05,
                             input="complete", capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "complete\n")
        self.assertEqual(result.stderr, "detail\n")

    def test_command_failure_is_not_retried(self):
        output = self.root / "attempts.txt"
        source = "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.open('a').write('attempt\\n'); sys.exit(7)"
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run_command([sys.executable, "-c", source, str(output)], stop_grace=0.1, check=True)
        self.assertEqual(raised.exception.returncode, 7)
        self.assertEqual(output.read_text(), "attempt\n")

    def test_work_deadline_and_lifecycle_overrides_are_rejected(self):
        for option in ("timeout", "pass_fds", "close_fds", "start_new_session"):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, "lifecycle"):
                run_command([sys.executable], stop_grace=0.1, **{option: 1})

    def wait_for_record(self, record):
        deadline = time.monotonic() + 5
        while not record.exists():
            if time.monotonic() >= deadline:
                self.fail("owned listener does not become ready")
            time.sleep(0.01)
        return json.loads(record.read_bytes())

    def assert_stopped(self, record):
        with self.assertRaises(ConnectionRefusedError), socket.create_connection(("127.0.0.1", record["port"]), timeout=1):
            self.fail("owned listener remains open")
        with self.assertRaises(ProcessLookupError):
            os.kill(record["pid"], 0)

    def terminate_owner(self, process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)

    def test_owner_interrupt_termination_and_death_close_and_reap_child(self):
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=number):
                record = self.root / f"listener-{number}.json"
                command = [sys.executable, str(COMMAND), "owner", str(record), "--ignore-term", "--stop-grace", "0.1"]
                owner = subprocess.Popen(command, env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.addCleanup(self.terminate_owner, owner)
                child = self.wait_for_record(record)
                os.kill(owner.pid, number)
                _, stderr = owner.communicate(timeout=5)
                self.assertNotEqual(owner.returncode, 0)
                self.assertIn(b"owned process group is stopped", stderr)
                self.assert_stopped(child)

    def test_successful_parent_cannot_leave_background_command_running(self):
        record = self.root / "background.json"
        command = [sys.executable, str(COMMAND), "background", str(record), "--stop-grace", "0.2"]
        result = run_command(command, stop_grace=0.2, capture_output=True, text=True, env=self.environment)
        self.assertEqual(result.returncode, 1)
        self.assertIn("incomplete: exit", result.stderr)
        self.assert_stopped(json.loads(record.read_bytes()))

    def test_publication_lock_lasts_through_child_cleanup_after_owner_death(self):
        record = self.root / "locked-listener.json"
        build = self.root / "publication"
        command = [sys.executable, str(COMMAND), "owner", str(record), "--ignore-term",
                   "--stop-grace", "1", "--lock-build", str(build)]
        owner = subprocess.Popen(command, env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.terminate_owner, owner)
        child = self.wait_for_record(record)
        owner.kill()
        owner.wait(timeout=5)
        with self.assertRaisesRegex(RuntimeError, "publisher lock"), publication_lock(build):
            self.fail("publication lock is released while the owned child is still draining")
        owner.communicate(timeout=5)
        self.assert_stopped(child)
        with publication_lock(build):
            self.assertTrue((build / ".publisher.lock").is_file())

    def test_configuration_requires_current_schema_and_explicit_shutdown_policy(self):
        source = (ROOT / "publisher.example.toml").read_text()
        path = self.root / "publisher.toml"
        for text in (source.replace("schema = 2", "schema = 1"),
                     source.replace("stop_grace_seconds = 10", "patience_seconds = 90"),
                     source.replace("stop_grace_seconds = 10", "stop_grace_seconds = 0")):
            with self.subTest(configuration=text[:16]), self.assertRaises(ValueError):
                path.write_text(text)
                load(path)


class ReadbackTests(unittest.TestCase):
    def test_progressing_readback_can_outlive_socket_inactivity_limit(self):
        body = b"0123456789"

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                for value in body:
                    self.wfile.write(bytes((value,)))
                    self.wfile.flush()
                    time.sleep(0.04)

            def log_message(self, *_):
                pass

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                started = time.monotonic()
                verify_download(f"http://127.0.0.1:{server.server_port}/data", hashlib.sha256(body).hexdigest(), len(body), 0.15)
                self.assertGreater(time.monotonic() - started, 0.15)
            finally:
                server.shutdown()
                thread.join()
