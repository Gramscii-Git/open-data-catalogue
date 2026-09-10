"""Document independently pinned catalogue and availability releases truthfully."""

import hashlib
import html
import json
import tarfile
from collections import Counter, defaultdict
from string import Template

from . import viewer
from .archive import QualityError, inspect_archive
from .availability import inspect_availability, policy_from
from .documentation_releases import load as load_releases
from .publish import file_url, upload_files, verify_download
from .runtime import remaining


def prepare(directory, config, catalogue_path, catalogue_revision, releases_path, template_path, viewer_path):
    tables = viewer.load(viewer_path)
    releases = load_releases(releases_path)
    try:
        catalogue = inspect_archive(catalogue_path, config["quality"])
        accepted = True
    except QualityError as error:
        catalogue, accepted = error.report, False
    hub = config["hub"]
    catalogue_url = file_url(hub, catalogue_revision, hub["archive"])
    archives, reports = {"catalogue": catalogue_path}, {"catalogue": catalogue}
    downloads = [(catalogue_url, catalogue)]
    index_rows, coverage = [], []
    for name, release in releases.items():
        report = inspect_availability(release["archive"], policy_from(release["policy"]))
        archives[name], reports[name] = release["archive"], report
        url = file_url(hub, release["revision"], f"{release['destination']}/availability.tar.gz")
        downloads.append((url, report))
        index_rows.append(
            f"| [{name}]({url}) | {report['manifest']['taken_at']} | {report['tables']['datasets.jsonl']:,} "
            f"| {report['tables']['partitions.jsonl']:,} | {report['tables']['combinations.jsonl']:,} "
            f"| {report['bytes']:,} | `{report['sha256']}` |"
        )
        coverage.append(coverage_rows(release["archive"], name, url))
    for url, report in downloads:
        verify_download(url, report["sha256"], report["bytes"], remaining(config, hub["timeout_seconds"]),
                        deadline=config.get("run_deadline"))
    (directory / "catalogue-quality.json").write_text(json.dumps({
        "accepted": accepted, "policy": config["quality"], "report": catalogue,
    }, indent=2), encoding="utf-8")
    values = {
        "viewer_metadata": viewer.prepare(directory, tables, archives, reports),
        "catalogue_taken_at": catalogue["manifest"]["taken_at"],
        "catalogue_datasets": str(catalogue["tables"]["opendata_catalog"]),
        "catalogue_url": catalogue_url, "catalogue_sha256": catalogue["sha256"],
        "catalogue_bytes": str(catalogue["bytes"]),
        "catalogue_status": "passes" if accepted else "does not pass",
        "catalogue_tables": "\n".join(f"| `{name}` | {count:,} |" for name, count in catalogue["tables"].items()),
        "catalogue_providers": "\n".join(f"| {name} | {count:,} |" for name, count in catalogue["providers"].items()),
        "catalogue_metrics": "\n".join(f"| {name} | {count:,} |" for name, count in catalogue["metrics"].items()),
        "availability_indexes": str(len(releases)),
        "availability_datasets": str(sum(reports[name]["tables"]["datasets.jsonl"] for name in releases)),
        "availability_combinations": f"{sum(reports[name]['tables']['combinations.jsonl'] for name in releases):,}",
        "availability_releases": "\n".join(index_rows),
        "availability_rows": "\n".join(coverage),
    }
    template = Template(template_path.read_text(encoding="utf-8"))
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError("Hub documentation must declare every artifact placeholder")
    (directory / "README.md").write_text(template.substitute(values), encoding="utf-8")
    return values


def coverage_rows(path, index, url):
    counts, periods, territories = Counter(), defaultdict(set), defaultdict(set)
    with tarfile.open(path, "r:gz") as archive:
        for line in archive.extractfile("combinations.jsonl"):
            row = json.loads(line)
            key = row["provider"], row["dataset_id"]
            counts[key] += 1
            periods[key].add(row["period"]["id"])
            if row["territory"] is not None:
                territories[key].add((row["territory"]["level"], row["territory"]["code"]))
        rows = []
        for line in archive.extractfile("datasets.jsonl"):
            row = json.loads(line)
            key = row["provider"], row["dataset_id"]
            identifiers = sorted(periods[key])
            endpoints = [identifiers[0], identifiers[-1]] if len(identifiers) > 1 else identifiers
            bounds = " / ".join(
                f"<code>{html.escape(value).replace('|', '&#124;')}</code>"
                for value in endpoints
            )
            rows.append(f"| [{index}]({url}) | {row['provider']} | `{row['dataset_id']}` | {row['period_kind']} | {len(identifiers):,} | {bounds} | {len(territories[key]):,} | {counts[key]:,} | {row['verified_at']} | {row['valid_until']} |")
    return "\n".join(rows)


def publish(directory, config):
    path = directory / "README.md"
    report = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    manifest = json.loads((directory / "viewer-manifest.json").read_bytes())
    files = ("README.md", "catalogue-quality.json", "viewer-manifest.json", *(row["path"] for row in manifest["files"]))
    return upload_files(directory, config, files, "README.md", report)
