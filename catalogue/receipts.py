"""Persist immutable artifact readback evidence independently of upload history."""

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .config import fields
from .publish import file_url, verify_download


def write_json(path, value, *, expected=None):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if expected is not None and path.read_bytes() != expected:
            raise ValueError("receipt or state changed concurrently; inspect the recorded evidence")
        if expected is None and path.exists():
            raise FileExistsError(path)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path.read_bytes()


def validate_pin(pin, hub, artifact):
    fields(pin, {"revision", "sha256", "bytes", "url"}, "artifact pin")
    if not isinstance(pin["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]):
        raise ValueError("artifact pin requires a SHA-256 digest")
    if type(pin["bytes"]) is not int or pin["bytes"] <= 0:
        raise ValueError("artifact pin requires a positive byte count")
    if pin["url"] != file_url(hub, pin["revision"], artifact):
        raise ValueError("artifact pin does not match the configured repository and artifact path")


def verify_local_archive(path, pin):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.stat().st_size != pin["bytes"] or digest != pin["sha256"]:
        raise ValueError(f"local archive differs from its verified artifact pin: {path}")


def verify_catalogue(config, archive, revision, digest, size, output):
    hub = config["hub"]
    pin = {"revision": revision, "sha256": digest, "bytes": size,
           "url": file_url(hub, revision, hub["archive"])}
    validate_pin(pin, hub, hub["archive"])
    record = {"schema_version": 1, "method": "immutable-readback", "artifact": pin,
              "started_at": datetime.now(UTC).isoformat(), "completed_at": None,
              "verified": False, "error": None}
    original = write_json(output, record)
    try:
        verify_local_archive(archive, pin)
        verify_download(pin["url"], digest, size, hub["timeout_seconds"])
    except BaseException as error:
        record.update(completed_at=datetime.now(UTC).isoformat(),
                      error={"type": type(error).__name__, "message": str(error)})
        write_json(output, record, expected=original)
        raise
    record.update(completed_at=datetime.now(UTC).isoformat(), verified=True)
    write_json(output, record, expected=original)
    return record


def read_verification(path, hub, artifact):
    record = json.loads(path.read_bytes())
    fields(record, {"schema_version", "method", "artifact", "started_at", "completed_at", "verified", "error"},
           "artifact verification receipt")
    if (type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["method"] != "immutable-readback" or record["verified"] is not True or record["error"] is not None):
        raise ValueError("artifact verification requires a successful immutable readback receipt")
    started, completed = (datetime.fromisoformat(record[key]) for key in ("started_at", "completed_at"))
    if started.utcoffset() is None or completed.utcoffset() is None or completed < started:
        raise ValueError("artifact verification requires ordered timezone-aware verification times")
    validate_pin(record["artifact"], hub, artifact)
    return record["artifact"]
