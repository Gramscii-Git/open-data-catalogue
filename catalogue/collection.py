"""Run an explicit collection plan with durable phase completion and native retries."""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .cli import harvester
from .config import fields, strings, text
from .config import load as load_publisher
from .runtime import process_lock, run_command


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    raw = path.read_bytes()
    plan = json.loads(raw)
    fields(plan, {"schema", "publisher", "retry_policy", "environment_sha256",
                  "harvester_revision", "provider", "steps", "directory",
                  "wait_for_current", "patience_seconds", "notification"}, "collection plan")
    if type(plan["schema"]) is not int or plan["schema"] != 2:
        raise ValueError("collection plan schema must be 2")
    for name in ("publisher", "retry_policy"):
        reference = plan[name]
        fields(reference, {"path", "sha256"}, name)
        reference["path"] = (path.parent / text(reference["path"], name)).resolve(strict=True)
        if digest(reference["path"]) != reference["sha256"]:
            raise ValueError(f"{name} differs from its declared digest")
    config = load_publisher(plan["publisher"]["path"])
    if digest(config["deployment"]["environment_file"]) != plan["environment_sha256"]:
        raise ValueError("harvester environment differs from its declared digest")
    revision = text(plan["harvester_revision"], "harvester_revision")
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("harvester_revision must be a complete Git commit")
    text(plan["provider"], "provider")
    steps = strings(plan["steps"], "steps")
    if len(set(steps)) != len(steps) or any(step not in {"sync", "structure"} for step in steps):
        raise ValueError("steps must be unique sync or structure commands")
    if steps == ["structure", "sync"]:
        raise ValueError("catalogue sync must precede structure collection")
    plan["directory"] = (path.parent / text(plan["directory"], "directory")).resolve()
    if type(plan["wait_for_current"]) is not bool:
        raise ValueError("wait_for_current must be boolean")
    patience = plan["patience_seconds"]
    if patience is not None:
        if type(patience) not in {int, float} or not math.isfinite(patience) or patience <= 0:
            raise ValueError("patience_seconds must be positive and finite, or null")
        if "structure" not in steps:
            raise ValueError("patience_seconds applies only to structure collection")
    fields(plan["notification"], {"complete", "failed"}, "notification")
    for status, command in plan["notification"].items():
        if command is not None:
            strings(command, f"notification.{status}")
    return plan, config, hashlib.sha256(raw).hexdigest()


def write_state(path, state):
    state["updated_at"] = datetime.now(UTC).isoformat()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".state-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"event": "collection_state", **state}), flush=True)


def read_state(path, plan, binding):
    if not path.exists():
        return {"schema": 1, "plan_sha256": binding, "completed": [],
                "status": "ready", "step": None, "error": None,
                "notification": "pending"}
    state = json.loads(path.read_text())
    fields(state, {"schema", "plan_sha256", "completed", "status", "step",
                   "error", "notification", "updated_at"}, "collection state")
    completed = state["completed"]
    if type(state["schema"]) is not int or state["schema"] != 1 or state["plan_sha256"] != binding:
        raise ValueError("collection state belongs to different inputs")
    if not isinstance(completed, list) or completed != plan["steps"][:len(completed)]:
        raise ValueError("completed collection steps are not a plan prefix")
    if state["status"] not in {"ready", "waiting", "running", "failed", "complete"}:
        raise ValueError("collection state has an invalid status")
    if state["status"] == "complete" and completed != plan["steps"]:
        raise ValueError("collection cannot be complete with pending steps")
    if state["notification"] not in {"pending", "sent", "disabled", "failed"}:
        raise ValueError("collection state has an invalid notification status")
    return state


def require_source(config, revision):
    deployment = config["deployment"]
    def git(*arguments):
        return run_command(["git", "-C", str(deployment["harvester"]), *arguments],
                           stop_grace=deployment["stop_grace_seconds"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if git("rev-parse", "HEAD") != revision:
        raise ValueError("harvester revision differs from the collection plan")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("collection requires a clean harvester source")


def notify(plan, config, state, path):
    command = plan["notification"][state["status"]]
    if state["notification"] in {"sent", "disabled"}:
        return
    if command is None:
        state["notification"] = "disabled"
    else:
        try:
            run_command(command, stop_grace=config["deployment"]["stop_grace_seconds"],
                        check=True)
        except Exception:
            state["notification"] = "failed"
            write_state(path, state)
            raise
        state["notification"] = "sent"
    write_state(path, state)


def run(plan_path, *, check=False):
    plan, config, binding = load(plan_path)
    require_source(config, plan["harvester_revision"])
    if check:
        print(json.dumps({"valid": True, "provider": plan["provider"],
                          "steps": plan["steps"], "plan_sha256": binding,
                          "started": False}))
        return
    directory = plan["directory"]
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    state_path = directory / "state.json"
    with process_lock(directory / ".collection.lock", label="collection"):
        state = read_state(state_path, plan, binding)
        if state["status"] == "complete":
            notify(plan, config, state, state_path)
            return
        state.update(status="waiting", step=None, error=None, notification="pending")
        write_state(state_path, state)
        build = config["deployment"]["build"]
        build.mkdir(parents=True, exist_ok=True)
        try:
            with process_lock(build / ".publisher.lock", label="publisher",
                              wait=plan["wait_for_current"]):
                for step in plan["steps"][len(state["completed"]):]:
                    current_plan, current_config, current_binding = load(plan_path)
                    if current_binding != binding:
                        raise ValueError("collection inputs change while the process is waiting")
                    require_source(current_config, current_plan["harvester_revision"])
                    state.update(status="running", step=step)
                    write_state(state_path, state)
                    patience = current_plan["patience_seconds"]
                    harvester(current_config, step, "--provider", plan["provider"],
                              "--retry-policy", str(plan["retry_policy"]["path"]),
                              *(("--patience", str(patience)) if step == "structure" and patience is not None else ()))
                    state["completed"].append(step)
                    state["step"] = None
                    write_state(state_path, state)
        except (Exception, KeyboardInterrupt) as error:
            state.update(status="failed", error={"type": type(error).__name__,
                         "returncode": error.returncode if isinstance(error, subprocess.CalledProcessError) else None})
            write_state(state_path, state)
            notify(plan, config, state, state_path)
            raise
        state.update(status="complete", step=None)
        write_state(state_path, state)
        notify(plan, config, state, state_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        run(args.plan.resolve(strict=True), check=args.check)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"collection failed: {error}", file=sys.stderr)
        return 1
    return 0
