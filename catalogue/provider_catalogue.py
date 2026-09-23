"""Publish one provider snapshot without replacing the combined catalogue."""

import hashlib
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from string import Template

from .archive import inspect_archive
from .publish import upload_files
from .viewer import load as load_viewer
from .viewer import project


def _destination(value: str) -> PurePosixPath:
    destination = PurePosixPath(value)
    if (
        destination.is_absolute()
        or ".." in destination.parts
        or str(destination) != value
        or len(destination.parts) < 2
    ):
        raise ValueError("provider catalogue destination must be a canonical nested path")
    return destination


def _catalogue_table(viewer_config: Path) -> dict:
    tables = [table for table in load_viewer(viewer_config) if table["name"] == "catalogue"]
    if len(tables) != 1:
        raise ValueError("viewer configuration requires exactly one catalogue table")
    return tables[0]


def _readme(template_path: Path, provider: str, report: dict, archive_name: str) -> str:
    template = Template(template_path.read_text(encoding="utf-8"))
    values = {
        "provider": provider,
        "taken_at": report["manifest"]["taken_at"],
        "datasets": str(report["tables"]["opendata_catalog"]),
        "documents": str(report["tables"]["opendata_documents"]),
        "archive": archive_name,
        "sha256": report["sha256"],
        "bytes": str(report["bytes"]),
    }
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError("provider README template must declare every release placeholder exactly")
    return template.substitute(values)


def prepare(
    source: Path,
    directory: Path,
    provider: str,
    destination: str,
    minimum_datasets: int,
    config: dict,
    readme_template: Path,
    viewer_config: Path,
) -> tuple[dict, tuple[str, ...], str]:
    """Validate and stage one provider archive and its directly browsable rows."""
    target = directory / _destination(destination)
    target.mkdir(parents=True)
    archive = target / config["hub"]["archive"]
    shutil.copyfile(source, archive)
    report = inspect_archive(
        archive,
        config["quality"],
        required_providers={provider},
        minimum_datasets=minimum_datasets,
    )
    (target / "manifest.json").write_text(
        json.dumps(report["manifest"], indent=2), encoding="utf-8"
    )
    (target / "quality.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (target / "SHA256SUMS").write_text(
        f"{report['sha256']}  {archive.name}\n", encoding="utf-8"
    )
    (target / "README.md").write_text(
        _readme(readme_template, provider, report, archive.name), encoding="utf-8"
    )

    table = _catalogue_table(viewer_config)
    viewer = target / "catalogue.jsonl"
    rows = 0
    with tarfile.open(archive, "r:gz") as held, viewer.open("x", encoding="utf-8") as output:
        for line in held.extractfile("opendata_catalog.jsonl"):
            row = project(json.loads(line), table["columns"])
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            rows += 1
    if rows != report["tables"]["opendata_catalog"]:
        raise ValueError("provider viewer row count differs from its validated archive")
    viewer_sha256 = hashlib.sha256(viewer.read_bytes()).hexdigest()
    (target / "viewer.json").write_text(
        json.dumps({
            "schema_version": 1,
            "config_name": f"{provider}_catalogue",
            "rows": rows,
            "path": "catalogue.jsonl",
            "sha256": viewer_sha256,
            "source_sha256": report["sha256"],
        }, indent=2),
        encoding="utf-8",
    )
    relative = PurePosixPath(destination)
    files = tuple(str(relative / name) for name in (
        archive.name,
        "manifest.json",
        "quality.json",
        "SHA256SUMS",
        "README.md",
        "catalogue.jsonl",
        "viewer.json",
    ))
    return report, files, str(relative / archive.name)


def publish(
    source: Path,
    directory: Path,
    provider: str,
    destination: str,
    minimum_datasets: int,
    config: dict,
    readme_template: Path,
    viewer_config: Path,
) -> dict:
    report, files, archive = prepare(
        source,
        directory,
        provider,
        destination,
        minimum_datasets,
        config,
        readme_template,
        viewer_config,
    )
    return upload_files(directory, config, files, archive, report)
