"""The README a reader of the S3 bucket finds beside the catalogue, written from a template and the export's own
manifest (s3_export), so every number it gives is the release's: the datasets, the providers, the snapshot's time,
the archive's SHA-256, each table's rows and the dimensions of the passages' vectors, with the providers grouped and
the tables described as `s3-readme.json` declares. A provider or a table of the release the declaration does not name,
or one it names the release does not hold, refuses the README rather than leave it wrong."""

import json
from datetime import UTC, datetime
from pathlib import Path
from string import Template

WIDTH = 96
GROUP_COLUMN = 25
ROWS_END = 34
DESCRIPTION_COLUMN = 39


def load(path: Path) -> dict:
    """The declaration of the README's provider groups, each a label and its providers with an optional note, and
    of each table's description."""
    declared = json.loads(path.read_text(encoding="utf-8"))
    if set(declared) != {"groups", "tables"} or not declared["groups"] or not declared["tables"]:
        raise ValueError("the S3 README declaration names its provider groups and its tables")
    if any(not isinstance(group, dict) or set(group) != {"label", "providers", "notes"} for group in declared["groups"]):
        raise ValueError("an S3 README group names its label, its providers and its notes, empty when it has none")
    named = [provider for group in declared["groups"] for provider in group["providers"]]
    if len(named) != len(set(named)):
        raise ValueError("a provider belongs to one group of the S3 README")
    if any(not set(group["notes"]) <= set(group["providers"]) for group in declared["groups"]):
        raise ValueError("an S3 README group notes only its own providers")
    return declared


def providers(manifest: dict) -> set[str]:
    """The providers whose datasets the release's catalogue holds: a provider every dataset of which was left out
    is a partition of the exclusions alone."""
    return {part.removeprefix("provider=") for path in manifest["files"] if path.startswith("opendata_catalog/")
            for part in path.split("/") if part.startswith("provider=")}


def _hanging(head: str, atoms: list[str], column: int) -> list[str]:
    """`atoms` filled after `head` up to WIDTH, the following lines indented to `column`; an atom is never cut."""
    lines, line = [], ""
    for atom in atoms:
        if line and column + len(line) + 1 + len(atom) > WIDTH:
            lines.append(line)
            line = atom
        else:
            line = f"{line} {atom}" if line else atom
    lines.append(line)
    return [head + " " * max(1, column - len(head)) + lines[0], *(" " * column + rest for rest in lines[1:])]


def written(template: str, manifest: dict, declared: dict) -> str:
    """The README of a release's bucket: `template` with the release's numbers and the declared groups and tables."""
    if manifest["schema"] != 2:
        raise ValueError("the S3 README is written from a schema 2 manifest, which names the passages' embedder")
    held, named = providers(manifest), {provider for group in declared["groups"] for provider in group["providers"]}
    if held != named:
        raise ValueError(f"the S3 README groups differ from the release's providers: not grouped {sorted(held - named)}, "
                         f"not in the release {sorted(named - held)}")
    if set(manifest["tables"]) != set(declared["tables"]):
        raise ValueError("the S3 README describes other tables than the release holds")
    groups = []
    for group in declared["groups"]:
        listed = [f"{provider} ({group['notes'][provider]})" if provider in group["notes"] else provider
                  for provider in group["providers"]]
        groups.extend(_hanging(group["label"], [f"{item}," for item in listed[:-1]] + listed[-1:], GROUP_COLUMN))
    tables = []
    for name, description in declared["tables"].items():
        rows = f"{manifest['tables'][name]['rows']:,}"
        tables.extend(_hanging(name + " " + rows.rjust(ROWS_END - len(name) - 1), description.split(), DESCRIPTION_COLUMN))
    taken = datetime.fromisoformat(manifest["taken_at"]).astimezone(UTC)
    return Template(template).substitute(
        datasets=f"{manifest['tables']['opendata_catalog']['rows']:,}", providers=len(held),
        taken_at=taken.strftime("%Y-%m-%dT%H:%M:%SZ"), archive_sha256=manifest["archive"]["sha256"],
        dimensions=manifest["passages"]["embedder"]["dimensions"],
        provider_groups="\n".join(groups), tables="\n".join(tables))
