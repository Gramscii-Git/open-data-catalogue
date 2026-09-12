"""Publish independently validated availability without replacing discovery tables."""

import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from string import Template

from .archive import digest
from .availability import _sha, policy_from
from .availability_build import verify_build
from .availability_scope import verify_inventory_scope
from .publish import upload_files


def prepare(source, directory, destination, policy_path, template_path, *, now, provenance_sha256=None):
    prefix = PurePosixPath(destination)
    if prefix.is_absolute() or not prefix.parts or any(part in {".", ".."} for part in prefix.parts):
        raise ValueError("availability destination must be a relative repository directory")
    if str(prefix) != destination:
        raise ValueError("availability destination must be a canonical repository directory")
    policy = policy_from(policy_path)
    provenance_path = source / "offline-provenance.json"
    if provenance_path.exists() != (provenance_sha256 is not None):
        raise ValueError("offline availability requires its explicit verified provenance publication path")
    provenance = None
    if provenance_sha256 is not None:
        _sha(provenance_sha256)
        if provenance_path.is_symlink() or provenance_path.stat().st_size > policy["max_line_bytes"] or digest(provenance_path) != provenance_sha256:
            raise ValueError("offline availability provenance changed before publication")
        provenance = json.loads(provenance_path.read_bytes())
    specification = json.loads((source / "scope.json").read_bytes())
    inventories = json.loads((source / "inventories.json").read_bytes())
    verify_inventory_scope(specification, inventories)
    exported = json.loads((source / "quality.json").read_bytes())
    archive = source / "availability.tar.gz"
    report = verify_build(archive, exported, specification, policy)
    if provenance is not None and (provenance["archive"]["sha256"] != report["sha256"]
                                   or provenance["archive"]["bytes"] != report["bytes"]
                                   or provenance["report"] != report):
        raise ValueError("offline provenance identifies a different validated availability archive")
    rows = []
    with tarfile.open(archive, "r:gz") as held:
        for line in held.extractfile("datasets.jsonl"):
            dataset = json.loads(line)
            if not datetime.fromisoformat(dataset["verified_at"]) <= now < datetime.fromisoformat(dataset["valid_until"]):
                raise ValueError("availability evidence is expired or not yet valid; rebuild the declared scope")
            rows.append(f"| {dataset['provider']} | `{dataset['dataset_id']}` | {dataset['valid_until']} |")
    target = directory / destination
    target.mkdir(parents=True)
    shutil.copyfile(archive, target / archive.name)
    shutil.copyfile(source / "inventories.json", target / "inventories.json")
    for name, value in (("manifest.json", report["manifest"]), ("quality.json", report), ("scope.json", specification)):
        (target / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
    (target / "SHA256SUMS").write_text(f"{report['sha256']}  {archive.name}\n", encoding="utf-8")
    template = Template(template_path.read_text(encoding="utf-8"))
    values = {
        "taken_at": report["manifest"]["taken_at"], "sha256": report["sha256"],
        "bytes": str(report["bytes"]), "dataset_rows": "\n".join(rows),
        "combinations": str(report["tables"]["combinations.jsonl"]),
        "partitions": str(report["tables"]["partitions.jsonl"]),
    }
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError("availability README must declare every publication placeholder")
    (target / "README.md").write_text(template.substitute(values), encoding="utf-8")
    files = tuple(str(prefix / name) for name in (
        "availability.tar.gz", "manifest.json", "quality.json", "scope.json", "inventories.json", "SHA256SUMS", "README.md",
    ))
    if provenance is not None:
        shutil.copyfile(provenance_path, target / provenance_path.name)
        if digest(target / provenance_path.name) != provenance_sha256:
            raise ValueError("offline provenance changed during publication staging")
        files += (str(prefix / provenance_path.name),)
        report = {**report, "offline_provenance_sha256": provenance_sha256, "input_manifest_sha256": provenance["provenance_sha256"]}
    return report, files


def publish(source, directory, destination, config, policy_path, template_path):
    report, files = prepare(source, directory, destination, policy_path, template_path, now=datetime.now(UTC))
    return upload_files(directory, config, files, f"{destination}/availability.tar.gz", report)
