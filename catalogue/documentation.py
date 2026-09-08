"""Document independently pinned catalogue and availability releases truthfully."""

import hashlib
import json
import tarfile
from collections import Counter, defaultdict
from string import Template

from . import viewer
from .archive import QualityError, inspect_archive
from .availability import inspect_availability, policy_from
from .publish import file_url, upload_files, verify_download


def prepare(directory, config, catalogue_path, catalogue_revision, availability_path, availability_revision, policy_path, template_path, viewer_path):
    tables = viewer.load(viewer_path)
    try:
        catalogue = inspect_archive(catalogue_path, config["quality"])
        accepted = True
    except QualityError as error:
        catalogue, accepted = error.report, False
    availability = inspect_availability(availability_path, policy_from(policy_path))
    hub = config["hub"]
    catalogue_url = file_url(hub, catalogue_revision, hub["archive"])
    availability_url = file_url(hub, availability_revision, "availability/availability.tar.gz")
    for url, report in ((catalogue_url, catalogue), (availability_url, availability)):
        verify_download(url, report["sha256"], report["bytes"], hub["timeout_seconds"])
    (directory / "catalogue-quality.json").write_text(json.dumps({
        "accepted": accepted, "policy": config["quality"], "report": catalogue,
    }, indent=2), encoding="utf-8")
    values = {
        "viewer_metadata": viewer.prepare(directory, tables,
                                          {"catalogue": catalogue_path, "availability": availability_path},
                                          {"catalogue": catalogue, "availability": availability}),
        "catalogue_taken_at": catalogue["manifest"]["taken_at"],
        "catalogue_datasets": str(catalogue["tables"]["opendata_catalog"]),
        "catalogue_url": catalogue_url, "catalogue_sha256": catalogue["sha256"],
        "catalogue_bytes": str(catalogue["bytes"]),
        "catalogue_status": "passes" if accepted else "does not pass",
        "catalogue_tables": "\n".join(f"| `{name}` | {count:,} |" for name, count in catalogue["tables"].items()),
        "catalogue_providers": "\n".join(f"| {name} | {count:,} |" for name, count in catalogue["providers"].items()),
        "catalogue_metrics": "\n".join(f"| {name} | {count:,} |" for name, count in catalogue["metrics"].items()),
        "availability_url": availability_url, "availability_taken_at": availability["manifest"]["taken_at"],
        "availability_sha256": availability["sha256"], "availability_bytes": str(availability["bytes"]),
        "availability_datasets": str(availability["tables"]["datasets.jsonl"]),
        "availability_partitions": str(availability["tables"]["partitions.jsonl"]),
        "availability_combinations": f"{availability['tables']['combinations.jsonl']:,}",
        "availability_rows": coverage_rows(availability_path),
    }
    template = Template(template_path.read_text(encoding="utf-8"))
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError("Hub documentation must declare every artifact placeholder")
    (directory / "README.md").write_text(template.substitute(values), encoding="utf-8")
    return values


def coverage_rows(path):
    counts, periods, territories = Counter(), defaultdict(set), defaultdict(set)
    with tarfile.open(path, "r:gz") as archive:
        for line in archive.extractfile("combinations.jsonl"):
            row = json.loads(line)
            key = row["provider"], row["dataset_id"]
            counts[key] += 1
            periods[key].add(row["period"]["id"])
            territories[key].add((row["territory"]["level"], row["territory"]["code"]))
        rows = []
        for line in archive.extractfile("datasets.jsonl"):
            row = json.loads(line)
            key = row["provider"], row["dataset_id"]
            rows.append(f"| {row['provider']} | `{row['dataset_id']}` | {', '.join(sorted(periods[key]))} | {len(territories[key]):,} | {counts[key]:,} | {row['valid_until']} |")
    return "\n".join(rows)


def publish(directory, config):
    path = directory / "README.md"
    report = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    manifest = json.loads((directory / "viewer-manifest.json").read_bytes())
    files = ("README.md", "catalogue-quality.json", "viewer-manifest.json", *(row["path"] for row in manifest["files"]))
    return upload_files(directory, config, files, "README.md", report)
