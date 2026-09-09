"""Prepare a harvester-built index and verify its exact publisher-declared scope."""

import hashlib
import json
import shutil
from itertools import product
from pathlib import Path

from .availability import inspect_availability, policy_from
from .availability_scope import resolve, verify_inventory_scope


def verify_build(archive, exported, specification, policy):
    report = inspect_availability(archive, policy)
    for field in ("sha256", "bytes", "manifest"):
        if exported[field] != report[field]:
            raise ValueError(f"availability producer {field} disagrees with the validated archive")
    requested = {
        (row["provider"], row["dataset_id"]): row for row in specification["datasets"]
    }
    if len(requested) != len(specification["datasets"]):
        raise ValueError("publisher availability scope contains duplicate datasets")
    actual = {
        (row["provider"], row["dataset_id"]): row["scope"] for row in report["datasets"]
    }
    if set(actual) != set(requested) or any(
        actual[key] != {"request_grid": scope, "consistency": "per-response"}
        for key, scope in requested.items()
    ):
        raise ValueError("built availability does not match the publisher's exact dataset scope")
    for dataset in report["datasets"]:
        scope = requested[dataset["provider"], dataset["dataset_id"]]
        names = sorted(scope["varying"])
        expected = set()
        for values in product(*(scope["varying"][name] for name in names)):
            request = {
                "arguments": {"dataset": scope["dataset_id"], **scope["arguments"], **dict(zip(names, values, strict=True))},
                "when": scope["when"],
            }
            expected.add(hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
        if set(dataset["partitions"]) != expected:
            raise ValueError("built availability omits or substitutes publisher-requested partitions")
    return report


def captured_scope(scope_path, inventory_path, inventory_sha256):
    specification = json.loads(scope_path.read_bytes())
    if set(specification) != {"schema_version", "limits", "datasets"} or specification["schema_version"] != 1:
        raise ValueError("captured-source reconstruction requires an explicitly resolved version-1 scope")
    evidence = inventory_path.read_bytes()
    if hashlib.sha256(evidence).hexdigest() != inventory_sha256:
        raise ValueError("captured inventory evidence differs from its explicit digest pin")
    inventories = json.loads(evidence)
    verify_inventory_scope(specification, inventories)
    return specification, inventories


def prepare(directory, config, scope_path, policy_path, harvester, *, capture=None):
    if capture is None:
        specification, inventories = resolve(json.loads(scope_path.read_bytes()))
        source_arguments = []
    else:
        specification, inventories = captured_scope(scope_path, capture["inventory_evidence"], capture["inventory_sha256"])
        source_arguments = ["--capture", str(capture["directory"]), "--capture-manifest", str(capture["manifest"]),
                            "--capture-sha256", capture["sha256"]]
    resolved_path = directory / "scope.json"
    resolved_path.write_text(json.dumps(specification, indent=2), encoding="utf-8")
    (directory / "inventories.json").write_text(json.dumps(inventories, indent=2), encoding="utf-8")
    policy = policy_from(policy_path)
    requested_providers = {row["provider"] for row in specification["datasets"]}
    if requested_providers != set(policy["providers"]):
        raise ValueError("availability scope and validation policy require different providers")
    contract = harvester(config, "--availability-contract", capture=True).strip()
    if contract != "1":
        raise ValueError("harvester availability construction contract must be 1")
    produced = json.loads(harvester(
        config, "index-availability", "--spec", str(resolved_path.resolve()),
        "--to", str(directory / "source"), *source_arguments, capture=True,
    ))
    archive = directory / "source" / "availability.tar.gz"
    if Path(produced["archive"]).resolve() != archive.resolve():
        raise ValueError("harvester returned an archive outside its assigned output directory")
    report = verify_build(archive, produced, specification, policy)
    shutil.copyfile(archive, directory / archive.name)
    for name, value in (
        ("quality.json", report), ("manifest.json", report["manifest"]),
        ("scope.json", specification),
    ):
        (directory / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
    (directory / "SHA256SUMS").write_text(
        f"{report['sha256']}  {archive.name}\n", encoding="utf-8",
    )
    return report
