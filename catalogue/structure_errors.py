"""Classify stored structure errors against a provider's declared permanent answers."""

import json
import re
import tarfile
from functools import cache
from pathlib import Path

# The parts of an SDMX dataflow reference a declared template may name, as SDG declares them.
REFERENCE_PARTS = {
    "agency": r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*)*",
    "id": r"[A-Za-z0-9_@$-]+",
    "version": r"[0-9]+(?:\.[0-9]+)*",
}


@cache
def template_pattern(template: str) -> re.Pattern:
    pattern, named = "", set()
    for index, piece in enumerate(re.split(r"\{([a-z]+)\}", template)):
        if index % 2 == 0:
            pattern += re.escape(piece)
        elif piece in named:
            pattern += f"(?P={piece})"
        else:
            pattern += f"(?P<{piece}>{REFERENCE_PARTS[piece]})"
            named.add(piece)
    return re.compile(pattern)


def declared_permanent(definition: dict, error: str) -> bool:
    """Whether a stored error is the bare provider answer a declared dataflow rule matches."""
    if definition.get("driver") != "sdmx":
        return False
    detail, separator, body = error.partition(": ")
    prefix = f"{definition['id']} answered "
    status = detail[len(prefix):]
    if not separator or not detail.startswith(prefix) or not status.isdigit():
        return False
    return any(
        rule["status"] == int(status) and template_pattern(rule["body_template"]).fullmatch(body) is not None
        for rule in definition["extra"]["dataflow_permanent_errors"]
    )


def permanent_structure_errors(path: Path) -> list[dict]:
    """The archive's structure errors its own document contract declares permanent."""
    with tarfile.open(path, "r:gz") as archive:
        providers = json.load(archive.extractfile("manifest.json"))["document_contract"]["rendering"]["providers"]
        return [
            {"provider": row["provider"], "dataset_id": row["dataset_id"], "error": row["error"]}
            for row in map(json.loads, archive.extractfile("opendata_structures.jsonl"))
            if isinstance(row["error"], str) and declared_permanent(providers[row["provider"]], row["error"])
        ]
