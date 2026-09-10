"""Validate the complete set of immutable availability publications on a Hub card."""

import json
import re
from pathlib import PurePosixPath


def load(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if set(config) != {"schema_version", "indexes"} or config["schema_version"] != 1:
        raise ValueError("unsupported documentation releases configuration")
    indexes = config["indexes"]
    if not isinstance(indexes, dict) or not indexes:
        raise ValueError("documentation indexes must be explicit and nonempty")
    destinations = set()
    for name, release in indexes.items():
        if name == "catalogue" or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError("documentation index names must be canonical and distinct from catalogue")
        if not isinstance(release, dict) or set(release) != {"archive", "revision", "destination", "policy"}:
            raise ValueError("documentation release fields are incomplete or unknown")
        if not isinstance(release["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", release["revision"]):
            raise ValueError("documentation revisions must be immutable full commit hashes")
        destination = release["destination"]
        if not isinstance(destination, str):
            raise TypeError("documentation destinations must be strings")
        prefix = PurePosixPath(destination)
        if prefix.is_absolute() or not prefix.parts or ".." in prefix.parts or str(prefix) != destination:
            raise ValueError("documentation destinations must be canonical relative directories")
        if destination in destinations:
            raise ValueError("documentation index destinations must be distinct")
        destinations.add(destination)
        for key in ("archive", "policy"):
            if not isinstance(release[key], str) or not release[key].strip():
                raise ValueError(f"documentation {key} path is required")
            release[key] = (path.parent / release[key]).resolve(strict=True)
    return indexes
