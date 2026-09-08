"""Publish independently validated availability without replacing discovery tables."""

import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from string import Template

from .availability import policy_from
from .availability_build import verify_build
from .publish import upload_files


def prepare(source, directory, destination, policy_path, template_path, *, now):
    prefix = PurePosixPath(destination)
    if prefix.is_absolute() or not prefix.parts or any(part in {".", ".."} for part in prefix.parts):
        raise ValueError("availability destination must be a relative repository directory")
    if str(prefix) != destination:
        raise ValueError("availability destination must be a canonical repository directory")
    policy = policy_from(policy_path)
    specification = json.loads((source / "scope.json").read_bytes())
    exported = json.loads((source / "quality.json").read_bytes())
    archive = source / "availability.tar.gz"
    report = verify_build(archive, exported, specification, policy)
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
        "availability.tar.gz", "manifest.json", "quality.json", "scope.json", "SHA256SUMS", "README.md",
    ))
    return report, files


def publish(source, directory, destination, config, policy_path, template_path):
    report, files = prepare(source, directory, destination, policy_path, template_path, now=datetime.now(UTC))
    return upload_files(directory, config, files, f"{destination}/availability.tar.gz", report)
