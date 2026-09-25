"""Prepare and document a validated discovery snapshot from the harvester."""

import html
import json
import shutil
from pathlib import Path
from string import Template

from .archive import QualityError, inspect_archive
from .structure_errors import permanent_structure_errors


def dataset_readme(template_path: Path, config: dict, report: dict, permanent_errors: list[dict]) -> str:
    template = Template(template_path.read_text(encoding="utf-8"))
    values = {
        "taken_at": report["manifest"]["taken_at"],
        "table_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["tables"].items()
        ),
        "provider_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["providers"].items()
        ),
        "quality_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["metrics"].items()
        ),
        "permanent_error_rows": "\n".join(
            f"| {row['provider']} | `{row['dataset_id']}` | {html.escape(row['error']).replace('|', '&#124;').replace(chr(10), ' ')} |"
            for row in permanent_errors
        ) or "| none | | |",
        "archive": config["hub"]["archive"],
        "sha256": report["sha256"],
        "bytes": str(report["bytes"]),
    }
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError(
            "dataset README template must declare every release placeholder exactly by name"
        )
    return template.substitute(values)


def _write_release(directory: Path, config: dict, archive: Path, report: dict) -> None:
    (directory / "manifest.json").write_text(
        json.dumps(report["manifest"], indent=2), encoding="utf-8"
    )
    (directory / "quality.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (directory / "SHA256SUMS").write_text(
        f"{report['sha256']}  {archive.name}\n", encoding="utf-8"
    )
    (directory / "README.md").write_text(
        dataset_readme(config["deployment"]["readme_template"], config, report, permanent_structure_errors(archive)),
        encoding="utf-8",
    )


def _inspect_release(directory: Path, config: dict, archive: Path) -> dict:
    try:
        report = inspect_archive(archive, config["quality"])
    except QualityError as error:
        (directory / "quality.json").write_text(
            json.dumps(error.report, indent=2), encoding="utf-8"
        )
        raise
    return report


def prepare_archive(directory: Path, config: dict, source: Path) -> dict:
    """Stage and validate an existing snapshot as the complete discovery release."""
    archive = directory / config["hub"]["archive"]
    shutil.copyfile(source, archive)
    report = _inspect_release(directory, config, archive)
    _write_release(directory, config, archive, report)
    return report


def prepare(directory: Path, config: dict, harvester) -> dict:
    archive = directory / config["hub"]["archive"]
    exported = json.loads(
        harvester(config, "export", "--to", str(archive), capture=True)
    )
    report = _inspect_release(directory, config, archive)
    if (
        exported["sha256"] != report["sha256"]
        or exported["bytes"] != report["bytes"]
        or exported["tables"] != report["tables"]
    ):
        raise ValueError("export report does not match the validated archive")
    _write_release(directory, config, archive, report)
    return report
