"""Validate scheduled publication scope, deployment receipts and freshness budgets."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from .availability import policy_from
from .config import fields, text
from .publish import file_url
from .viewer import load as load_viewer


def positive(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def name(value):
    if not isinstance(value, str) or value == "catalogue" or not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
        raise ValueError("update indexes must have canonical names distinct from catalogue")
    return value


def destination(value):
    prefix = PurePosixPath(text(value, "publication destination"))
    if prefix.is_absolute() or not prefix.parts or ".." in prefix.parts or str(prefix) != value:
        raise ValueError("publication destination must be a canonical relative directory")
    return value


def paths(row, names, base):
    for key in names:
        row[key] = str((base / text(row[key], key)).resolve(strict=True))


def receipt(path, hub, artifact):
    value = json.loads(path.read_bytes())
    fields(value, {"revision", "sha256", "bytes", "url", "verified"}, "publication receipt")
    if value["verified"] is not True or not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise ValueError("update state requires a verified publication and digest")
    positive(value["bytes"], "publication bytes")
    if value["url"] != file_url(hub, value["revision"], artifact):
        raise ValueError("update publication does not match the configured repository and artifact path")
    return value


def load_state(path, config):
    original = path.read_bytes()
    state = json.loads(original)
    fields(state, {"schema_version", "catalogue", "indexes"}, "update state")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise ValueError("update state schema must be 1")
    fields(state["catalogue"], {"archive", "publication"}, "catalogue state")
    paths(state["catalogue"], ("archive", "publication"), path.parent)
    catalogue = state["catalogue"]
    receipt(Path(catalogue["publication"]), config["hub"], config["hub"]["archive"])
    if not isinstance(state["indexes"], dict) or not state["indexes"]:
        raise ValueError("update state requires explicit availability indexes")
    destinations = set()
    for index, release in state["indexes"].items():
        name(index)
        fields(release, {"archive", "policy", "publication", "activation", "destination"}, "index state")
        paths(release, ("archive", "policy", "publication", "activation"), path.parent)
        prefix = destination(release["destination"])
        if prefix in destinations:
            raise ValueError("update index destinations must be distinct")
        destinations.add(prefix)
        published = receipt(Path(release["publication"]), config["hub"], f"{prefix}/availability.tar.gz")
        activated = json.loads(Path(release["activation"]).read_bytes())
        pin = {key: published[key] for key in ("url", "revision", "sha256", "bytes")}
        if (not isinstance(activated, dict) or activated.get("activated") is not True
                or activated.get("index") != index or activated.get("artifact") != pin
                or not isinstance(activated.get("snapshots"), dict)):
            raise ValueError("update state requires a confirmed matching consumer activation")
    return state, original


def verify_local_archive(path, published):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.stat().st_size != published["bytes"] or digest != published["sha256"]:
        raise ValueError(f"update archive differs from its verified publication receipt: {path}")


def load(path, config):
    plan = json.loads(path.read_bytes())
    fields(plan, {"schema_version", "state", "cadence", "discovery", "indexes", "documentation"}, "update plan")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ValueError("update plan schema must be 1")
    paths(plan, ("state",), path.parent)
    cadence = plan["cadence"]
    fields(cadence, {"interval_seconds", "maximum_run_seconds", "minimum_remaining_seconds"}, "update cadence")
    for key, value in cadence.items():
        positive(value, f"cadence.{key}")
    if cadence["maximum_run_seconds"] >= cadence["interval_seconds"]:
        raise ValueError("update run budget must be shorter than the scheduling interval")
    fields(plan["discovery"], {"action"}, "discovery update")
    if plan["discovery"]["action"] not in {"retain", "publish", "release"}:
        raise ValueError("discovery action must be retain, publish or release")
    document = plan["documentation"]
    fields(document, {"readme_template", "viewer_config"}, "update documentation")
    paths(document, ("readme_template", "viewer_config"), path.parent)
    state, _ = load_state(Path(plan["state"]), config)
    tables = load_viewer(Path(document["viewer_config"]))
    if {table["archive"] for table in tables} != {"catalogue", *state["indexes"]}:
        raise ValueError("update documentation must cover exactly the state archive set")
    if not isinstance(plan["indexes"], dict) or not plan["indexes"]:
        raise ValueError("update plan requires explicit indexes to rebuild")
    if not plan["indexes"].keys() <= state["indexes"].keys():
        raise ValueError("update indexes must already have explicit publication and activation state")
    source_budget = 0
    snapshot_destinations = set()
    for index, definition in plan["indexes"].items():
        name(index)
        fields(definition, {"scope", "policy", "destination", "readme_template", "snapshots"}, "index update")
        paths(definition, ("scope", "policy", "readme_template"), path.parent)
        if destination(definition["destination"]) != state["indexes"][index]["destination"]:
            raise ValueError("update cannot change a consumer's publication destination")
        scope = json.loads(Path(definition["scope"]).read_bytes())
        fields(scope, {"schema_version", "limits", "datasets", "inventories"}, "scheduled scope")
        if (type(scope["schema_version"]) is not int or scope["schema_version"] != 2
                or not isinstance(scope["datasets"], list) or not scope["datasets"]):
            raise ValueError("scheduled builds require an explicit version-2 publisher scope")
        source_budget += positive(scope["limits"]["operation_timeout_seconds"], "source operation timeout")
        providers = {row["provider"] for row in scope["datasets"]}
        if providers != set(policy_from(Path(definition["policy"]))["providers"]):
            raise ValueError("update scope and validation policy require different providers")
        freshness_budget = sum(cadence.values())
        for dataset in scope["datasets"]:
            if positive(dataset["valid_for_seconds"], "source evidence lifetime") < freshness_budget:
                raise ValueError(f"update cadence and run budget exceed evidence lifetime for {index}:{dataset['dataset_id']}")
        snapshot = definition["snapshots"]
        activated = json.loads(Path(state["indexes"][index]["activation"]).read_bytes())
        if snapshot is None:
            if activated["snapshots"]:
                raise ValueError("archived consumer providers require explicit snapshot rebuilds")
            continue
        fields(snapshot, {"providers", "shard_prefix_length", "destination"}, "snapshot update")
        selected = snapshot["providers"]
        if (not isinstance(selected, list) or not selected or any(not isinstance(item, str) for item in selected)
                or len(selected) != len(set(selected)) or not set(selected) <= providers
                or set(selected) != activated["snapshots"].keys()):
            raise ValueError("snapshot providers must exactly match the archived consumer providers")
        positive(snapshot["shard_prefix_length"], "snapshot shard prefix length")
        if snapshot["shard_prefix_length"] > hashlib.sha256().digest_size * 2:
            raise ValueError("snapshot shard prefix length exceeds the source digest length")
        prefix = destination(snapshot["destination"])
        if prefix in snapshot_destinations or prefix in {release["destination"] for release in state["indexes"].values()}:
            raise ValueError("snapshot and availability destinations must be distinct")
        snapshot_destinations.add(prefix)
    if source_budget >= cadence["maximum_run_seconds"]:
        raise ValueError("update run budget must include time beyond all source operation deadlines")
    return plan
