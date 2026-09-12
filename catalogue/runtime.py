"""Own command processes until completion or explicit owner shutdown."""

import argparse
import fcntl
import json
import math
import os
import queue
import signal
import stat
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_lock_descriptors = ContextVar("publisher_lock_descriptors", default=())


@contextmanager
def process_lock(path, *, label):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"{label} lock requires a regular file: {path}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"{label} lock is held by an execution or its draining command: {path}") from error
        os.ftruncate(descriptor, 0)
        os.write(descriptor, json.dumps({"owner_pid": os.getpid()}).encode())
        os.fsync(descriptor)
        token = _lock_descriptors.set((*_lock_descriptors.get(), descriptor))
        try:
            yield
        finally:
            _lock_descriptors.reset(token)
    finally:
        os.close(descriptor)


def run_command(arguments, *, stop_grace, **options):
    if os.name != "posix":
        raise RuntimeError("publisher command ownership requires POSIX process groups")
    if type(stop_grace) not in (int, float) or not math.isfinite(stop_grace) or stop_grace <= 0:
        raise ValueError("command stop grace must be positive and finite")
    forbidden = {"timeout", "start_new_session", "pass_fds", "close_fds"} & options.keys()
    if forbidden:
        raise ValueError(f"owned commands cannot override lifecycle options: {sorted(forbidden)}")
    check = options.pop("check", False)
    body = options.pop("input", None)
    if body is not None:
        if "stdin" in options:
            raise ValueError("input and stdin cannot both be supplied")
        options["stdin"] = subprocess.PIPE
    if options.pop("capture_output", False):
        if "stdout" in options or "stderr" in options:
            raise ValueError("capture_output and explicit output streams cannot be combined")
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reader, owner = os.pipe()
    try:
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--owner-fd", str(reader),
                   "--stop-grace", str(stop_grace), "--", *map(str, arguments)]
        process = subprocess.Popen(command, pass_fds=(reader, *_lock_descriptors.get()), start_new_session=True, **options)
    except BaseException:
        os.close(owner)
        raise
    finally:
        os.close(reader)
    try:
        stdout, stderr = process.communicate(body)
    except BaseException:
        blocked = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            os.close(owner)
            owner = None
            process.communicate()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
        raise
    finally:
        if owner is not None:
            os.close(owner)
    completed = subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


def signal_group(pid, number):
    try:
        os.killpg(pid, number)
    except ProcessLookupError:
        return False
    return True


def stop_group(process, grace):
    deadline = time.monotonic() + grace
    signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    if signal_group(process.pid, 0):
        threading.Event().wait(max(0, deadline - time.monotonic()))
        signal_group(process.pid, signal.SIGKILL)
    process.wait()


def supervise(arguments, owner_fd, stop_grace):
    events = queue.Queue()
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, lambda number, _: events.put(("signal", number)))

    def owner_closed():
        try:
            os.read(owner_fd, 1)
        finally:
            os.close(owner_fd)
            events.put(("owner_closed", None))

    threading.Thread(target=owner_closed, daemon=True).start()
    process = subprocess.Popen(arguments, start_new_session=True)
    try:
        threading.Thread(target=lambda: events.put(("exit", process.wait())), daemon=True).start()
        reason, status = events.get()
        if reason == "exit" and not signal_group(process.pid, 0):
            return status if status >= 0 else 128 - status
    finally:
        if process.poll() is None or signal_group(process.pid, 0):
            stop_group(process, stop_grace)
    print(f"publisher command is incomplete: {reason}; owned process group is stopped", file=sys.stderr, flush=True)
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-fd", type=int, required=True)
    parser.add_argument("--stop-grace", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not math.isfinite(args.stop_grace) or args.stop_grace <= 0:
        parser.error("stop grace must be positive and finite")
    if not args.command or args.command[0] != "--" or len(args.command) == 1:
        parser.error("an explicit command is required after --")
    return supervise(args.command[1:], args.owner_fd, args.stop_grace)


if __name__ == "__main__":
    raise SystemExit(main())
