"""Expose real process ownership and listener lifetime to publisher tests."""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
from contextlib import ExitStack
from pathlib import Path

from catalogue.cli import publication_lock
from catalogue.runtime import run_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("owner", "server", "background"))
    parser.add_argument("record", type=Path)
    parser.add_argument("--ignore-term", action="store_true")
    parser.add_argument("--stop-grace", type=float, required=True)
    parser.add_argument("--ready-fd", type=int)
    parser.add_argument("--lock-build", type=Path)
    args = parser.parse_args()
    command = [sys.executable, __file__, "server", str(args.record), "--stop-grace", str(args.stop_grace)]
    if args.ignore_term:
        command.append("--ignore-term")
    if args.mode == "owner":
        with ExitStack() as resources:
            if args.lock_build is not None:
                resources.enter_context(publication_lock(args.lock_build))
            return run_command(command, stop_grace=args.stop_grace, check=True).returncode
    if args.mode == "background":
        reader, writer = os.pipe()
        subprocess.Popen([*command, "--ready-fd", str(writer)], pass_fds=(writer,))
        os.close(writer)
        try:
            if os.read(reader, 1) != b"1":
                raise RuntimeError("background listener is not ready")
        finally:
            os.close(reader)
        return 0
    if args.ignore_term:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        pending = args.record.with_suffix(".pending")
        pending.write_text(json.dumps({"pid": os.getpid(), "supervisor": os.getppid(),
                                       "group": os.getpgrp(), "port": listener.getsockname()[1]}))
        pending.replace(args.record)
        if args.ready_fd is not None:
            os.write(args.ready_fd, b"1")
            os.close(args.ready_fd)
        threading.Event().wait()


if __name__ == "__main__":
    raise SystemExit(main())
