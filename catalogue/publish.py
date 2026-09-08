"""Publish one validated directory and verify its immutable revision."""

import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit


def revision_from_result(result: str, hub: dict) -> str:
    payload = json.loads(result)
    if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
        raise TypeError("hf upload must return JSON with a commit URL")
    parsed = urlsplit(payload["url"])
    base = urlsplit(hub["endpoint"])
    prefix = f"/datasets/{hub['repository']}/commit/"
    if (
        parsed.scheme != base.scheme
        or parsed.netloc != base.netloc
        or not parsed.path.startswith(prefix)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "upload result does not identify a commit of the configured dataset"
        )
    revision = parsed.path[len(prefix) :]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("upload result must identify an immutable commit")
    return revision


def file_url(hub: dict, revision: str, filename: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("download revision must be a full commit hash")
    return f"{hub['endpoint']}/datasets/{quote(hub['repository'], safe='/')}/resolve/{revision}/{quote(filename, safe='')}"


def verify_download(url: str, sha256: str, size: int, timeout: float) -> None:
    digest = hashlib.sha256()
    length = 0
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"published download returned HTTP {response.status}")
        while block := response.read(1024 * 1024):
            digest.update(block)
            length += len(block)
            if length > size:
                raise RuntimeError("published download exceeds the expected byte count")
    if length != size or digest.hexdigest() != sha256:
        raise RuntimeError(
            "published download does not match the release size and SHA-256"
        )


def upload(directory: Path, config: dict, report: dict) -> dict:
    hub = config["hub"]
    files = (hub["archive"], "manifest.json", "SHA256SUMS", "quality.json", "README.md")
    arguments = [
        *config["deployment"]["hf"],
        "upload",
        hub["repository"],
        str(directory),
        ".",
        "--repo-type",
        "dataset",
        "--revision",
        hub["branch"],
        "--commit-message",
        hub["commit_message"],
        "--json",
    ]
    for filename in files:
        arguments.extend(("--include", filename))
    completed = subprocess.run(
        arguments,
        env={**os.environ, "HF_ENDPOINT": hub["endpoint"]},
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    (directory / "upload-result.txt").write_text(completed.stdout, encoding="utf-8")
    revision = revision_from_result(completed.stdout, hub)
    publication = {
        "revision": revision,
        "sha256": report["sha256"],
        "bytes": report["bytes"],
    }
    publication["url"] = file_url(hub, revision, hub["archive"])
    (directory / "publication.json").write_text(
        json.dumps({**publication, "verified": False}, indent=2), encoding="utf-8"
    )
    for filename in files:
        path = directory / filename
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        verify_download(
            file_url(hub, revision, filename),
            digest,
            path.stat().st_size,
            hub["timeout_seconds"],
        )
    publication["verified"] = True
    (directory / "publication.json").write_text(
        json.dumps(publication, indent=2), encoding="utf-8"
    )
    return publication
