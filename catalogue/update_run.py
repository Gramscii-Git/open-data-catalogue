"""Run explicit publication stages with durable receipts and consumer pin checks."""

import json
import os
import sys
import tarfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import availability_build, availability_publish, documentation, snapshots
from .publish import upload
from .receipts import (
    read_verification,
    verify_catalogue,
    verify_local_archive,
    write_json,
)
from .runtime import remaining
from .update_plan import load_state, receipt


@contextmanager
def state_lock(path):
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise RuntimeError(f"update state lock exists; inspect its owning process: {lock}") from error
    try:
        yield
    finally:
        lock.rmdir()


def require_active(state, actual):
    if not isinstance(actual, dict) or set(actual) != {"indexes"} or not isinstance(actual["indexes"], dict):
        raise ValueError("consumer availability status has an invalid contract")
    if actual["indexes"].keys() != state["indexes"].keys():
        raise ValueError("consumer availability indexes differ from explicit update state")
    for name, release in state["indexes"].items():
        activated = json.loads(Path(release["activation"]).read_bytes())
        expected = {key: activated[key] for key in ("artifact", "snapshots")}
        if actual["indexes"][name] != expected:
            raise ValueError(f"consumer pin differs from update state for {name}; reconcile the actual activation receipts before a new run")


def require_fresh(archive, *, now, required_until):
    with tarfile.open(archive, "r:gz") as source:
        for line in source.extractfile("datasets.jsonl"):
            dataset = json.loads(line)
            if not datetime.fromisoformat(dataset["verified_at"]) <= now < datetime.fromisoformat(dataset["valid_until"]):
                raise ValueError("update evidence is expired or not yet valid; no freshness extension is permitted")
            if datetime.fromisoformat(dataset["valid_until"]) < required_until:
                raise ValueError(f"update evidence cannot cover its next declared run budget: {dataset['provider']}:{dataset['dataset_id']}")


def require_initial_coverage(plan, config, *, now, run_at_load):
    if type(run_at_load) is not bool:
        raise ValueError("schedule.run_at_load must be boolean")
    cadence = plan["cadence"]
    wait = 0 if run_at_load else cadence["interval_seconds"]
    required_until = now + timedelta(seconds=wait + cadence["maximum_run_seconds"] + cadence["minimum_remaining_seconds"])
    state, _ = load_state(Path(plan["state"]), config)
    for name in plan["indexes"]:
        release = state["indexes"][name]
        published = json.loads(Path(release["publication"]).read_bytes())
        archive = Path(release["archive"])
        verify_local_archive(archive, published)
        require_fresh(archive, now=now, required_until=required_until)


class Run:
    def __init__(self, directory, config):
        self.directory, self.config = directory, config

    def event(self, phase, status, **details):
        value = {"phase": phase, "status": status, "at": datetime.now(UTC).isoformat(), **details}
        with (self.directory / "progress.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(value), file=sys.stderr, flush=True)

    @contextmanager
    def record(self):
        self.event("update", "started")
        try:
            yield
        except BaseException as error:
            failure = {"complete": False, "error_type": type(error).__name__, "error": str(error)}
            write_json(self.directory / "failure.json", failure)
            self.event("update", "failed", **failure)
            raise

    def phase(self, name, operation):
        directory = self.directory / name
        directory.mkdir()
        self.event(name, "started", directory=str(directory))
        try:
            remaining(self.config)
            result = operation(directory)
            write_json(directory / "result.json", result)
            remaining(self.config)
        except BaseException as error:
            self.event(name, "failed", error_type=type(error).__name__, error=str(error))
            raise
        self.event(name, "complete", result=str(directory / "result.json"))
        return result


def run(directory, config, plan, harvester, prepare_catalogue):
    started = datetime.now(UTC)
    cadence = plan["cadence"]
    config = {**config, "run_deadline": time.monotonic() + cadence["maximum_run_seconds"]}
    execution = Run(directory, config)
    write_json(directory / "plan.json", plan)
    state_path = Path(plan["state"])
    with execution.record(), state_lock(state_path):
        state, original = load_state(state_path, config)
        write_json(directory / "initial-state.json", state)
        execution.phase("consumer-before", lambda _: preflight(state, config, harvester))
        action = plan["discovery"]["action"]
        if action != "retain":
            release_dir = directory / "discovery"
            execution.phase("discovery", lambda target: discovery_release(target, config, action, harvester, prepare_catalogue))
            state["catalogue"] = {"archive": str(release_dir / config["hub"]["archive"]),
                                  "verification": str(release_dir / "verification.json")}
            original = write_json(state_path, state, expected=original)
        required_until = started + timedelta(seconds=sum(cadence.values()))
        for name, definition in plan["indexes"].items():
            state["indexes"][name] = update_index(execution, name, definition, state["indexes"][name], required_until, harvester)
            original = write_json(state_path, state, expected=original)
        execution.phase("consumer-after", lambda _: preflight(state, config, harvester))
        releases = {"schema_version": 1, "indexes": {}}
        for name, release in state["indexes"].items():
            published = receipt(Path(release["publication"]), config["hub"], f"{release['destination']}/availability.tar.gz")
            releases["indexes"][name] = {"archive": release["archive"], "policy": release["policy"],
                                        "destination": release["destination"], "revision": published["revision"]}
        releases_path = directory / "documentation-releases.json"
        write_json(releases_path, releases)
        catalogue = state["catalogue"]
        published = read_verification(Path(catalogue["verification"]), config["hub"], config["hub"]["archive"])
        doc = plan["documentation"]
        execution.phase("documentation", lambda target: document_release(
            target, config, Path(catalogue["archive"]), published["revision"], releases_path,
            Path(doc["readme_template"]), Path(doc["viewer_config"]),
        ))
        result = {"complete": True, "directory": str(directory), "state": str(state_path),
                  "updated_indexes": list(plan["indexes"]), "discovery_action": action,
                  "documentation": str(directory / "documentation/publication.json")}
        write_json(directory / "complete.json", result)
        execution.event("update", "complete", result=str(directory / "complete.json"))
        return result


def preflight(state, config, harvester):
    actual = json.loads(harvester(config, "availability-status", capture=True))
    require_active(state, actual)
    catalogue = state["catalogue"]
    verified = read_verification(Path(catalogue["verification"]), config["hub"], config["hub"]["archive"])
    verify_local_archive(Path(catalogue["archive"]), verified)
    for release in state["indexes"].values():
        published = json.loads(Path(release["publication"]).read_bytes())
        verify_local_archive(Path(release["archive"]), published)
    return actual


def discovery_release(directory, config, action, harvester, prepare_catalogue):
    if harvester(config, "--release-contract", capture=True).strip() != "1":
        raise ValueError("harvester release contract must be 1")
    if action == "release":
        harvester(config, "sync")
        harvester(config, "structure", "--patience", str(config["deployment"]["patience_seconds"]))
        harvester(config, "enrich")
        harvester(config, "verify")
    report = prepare_catalogue(directory, config, harvester)
    published = upload(directory, config, report)
    verify_catalogue(config, directory / config["hub"]["archive"], published["revision"],
                     published["sha256"], published["bytes"], directory / "verification.json")
    return published


def activate(config, harvester, name, publication_path, expected, snapshot_paths):
    arguments = [] if snapshot_paths is None else ["--snapshot-publications", str(snapshot_paths)]
    result = json.loads(harvester(config, "activate-availability", "--index", name, "--publication", str(publication_path),
                                  "--expect-sha256", expected, *arguments, capture=True))
    publication = json.loads(publication_path.read_bytes())
    pin = {key: publication[key] for key in ("url", "revision", "sha256", "bytes")}
    if (not isinstance(result, dict) or result.get("activated") is not True or result.get("index") != name
            or result.get("artifact") != pin or not isinstance(result.get("previous"), dict)
            or result["previous"].get("sha256") != expected or not isinstance(result.get("snapshots"), dict)):
        raise ValueError("consumer did not confirm the requested availability activation")
    return result


def document_release(directory, config, archive, revision, releases, template, viewer):
    documentation.prepare(directory, config, archive, revision, releases, template, viewer)
    return documentation.publish(directory, config)


def update_index(execution, name, definition, previous_release, required_until, harvester):
    directory, config = execution.directory, execution.config
    source = directory / f"{name}-build"
    snapshot = definition["snapshots"]
    execution.phase(f"{name}-build", lambda target: availability_build.prepare(
        target, config, Path(definition["scope"]), Path(definition["policy"]), harvester,
        snapshot_providers=() if snapshot is None else snapshot["providers"],
        snapshot_shard_prefix_length=None if snapshot is None else snapshot["shard_prefix_length"],
    ))
    archive = source / "availability.tar.gz"
    require_fresh(archive, now=datetime.now(UTC), required_until=required_until)
    snapshot_paths = None
    if snapshot is not None:
        snapshot_dir = directory / f"{name}-snapshots"
        execution.phase(f"{name}-snapshots", lambda target: snapshots.publish(
            source / "source/snapshots", archive, target, snapshot["destination"], config, Path(definition["policy"]),
        ))
        snapshot_paths = directory / f"{name}-snapshot-publications.json"
        write_json(snapshot_paths, {provider: str(snapshot_dir / "publication.json") for provider in snapshot["providers"]})
    publication_dir = directory / f"{name}-publication"
    execution.phase(f"{name}-publication", lambda target: availability_publish.publish(
        source, target, definition["destination"], config, Path(definition["policy"]), Path(definition["readme_template"]),
    ))
    require_fresh(archive, now=datetime.now(UTC), required_until=required_until)
    previous = receipt(Path(previous_release["publication"]), config["hub"], f"{definition['destination']}/availability.tar.gz")
    publication_path = publication_dir / "publication.json"
    activation_dir = directory / f"{name}-activation"
    execution.phase(f"{name}-activation", lambda _: activate(
        config, harvester, name, publication_path, previous["sha256"], snapshot_paths,
    ))
    return {
        "archive": str(archive), "policy": definition["policy"], "destination": definition["destination"],
        "publication": str(publication_path), "activation": str(activation_dir / "result.json"),
    }
