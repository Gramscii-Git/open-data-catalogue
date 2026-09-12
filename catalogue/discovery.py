"""Prepare and document a validated discovery snapshot from the harvester."""

import json
from pathlib import Path
from string import Template

from .archive import QualityError, inspect_archive


def dataset_readme(template_path: Path, config: dict, report: dict) -> str:
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
        "archive": config["hub"]["archive"],
        "sha256": report["sha256"],
        "bytes": str(report["bytes"]),
    }
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError(
            "dataset README template must declare every release placeholder exactly by name"
        )
    return template.substitute(values)


def prepare(directory: Path, config: dict, harvester) -> dict:
    archive = directory / config["hub"]["archive"]
    exported = json.loads(
        harvester(config, "export", "--to", str(archive), capture=True)
    )
    try:
        report = inspect_archive(archive, config["quality"])
    except QualityError as error:
        (directory / "quality.json").write_text(
            json.dumps(error.report, indent=2), encoding="utf-8"
        )
        raise
    if (
        exported["sha256"] != report["sha256"]
        or exported["bytes"] != report["bytes"]
        or exported["tables"] != report["tables"]
    ):
        raise ValueError("export report does not match the validated archive")
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
        dataset_readme(config["deployment"]["readme_template"], config, report),
        encoding="utf-8",
    )
    return report
