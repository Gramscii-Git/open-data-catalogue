"""Bind historical quality statements to their exact published archive and report."""

import hashlib
import json
import re
import tarfile
from pathlib import PurePosixPath

from .archive import SCHEMA_VERSION, TABLE_KEYS, digest
from .config import fields, text
from .publish import file_url, verify_download
from .runtime import remaining


def status_path(value):
    path = PurePosixPath(text(value, "catalogue status artifact"))
    if (len(path.parts) != 1 or path.suffix != ".json" or str(path) != value
            or value in {"manifest.json", "quality.json", "catalogue-quality.json", "viewer-manifest.json", "publication.json"}):
        raise ValueError("catalogue status artifact must be a distinct root JSON filename")
    return value


def pin(value, base, hub, artifact):
    fields(value, {"path", "revision", "url", "sha256", "bytes"}, "published evidence pin")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
        raise ValueError("published evidence requires a SHA-256 digest")
    if type(value["bytes"]) is not int or value["bytes"] <= 0:
        raise ValueError("published evidence byte count must be positive")
    if not isinstance(value["revision"], str) or value["url"] != file_url(hub, value["revision"], artifact):
        raise ValueError("published evidence must identify the configured immutable artifact")
    path = (base / text(value["path"], "published evidence local path")).resolve(strict=True)
    if not path.is_file() or path.stat().st_size != value["bytes"] or digest(path) != value["sha256"]:
        raise ValueError("published evidence local size or digest differs from its pin")
    return {**value, "path": path}


def counts(value, name):
    if not isinstance(value, dict) or not value or any(
        not isinstance(key, str) or not key or type(count) is not int or count < 0
        for key, count in value.items()
    ):
        raise ValueError(f"published {name} must contain named nonnegative integer counts")


def read(path, config, *, verify_remote):
    value = json.loads(path.read_bytes())
    fields(value, {"schema_version", "archive", "quality_report"}, "published catalogue evidence")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("published catalogue evidence schema must be 1")
    archive = pin(value["archive"], path.parent, config["hub"], config["hub"]["archive"])
    quality = pin(value["quality_report"], path.parent, config["hub"], "catalogue-quality.json")
    raw = quality["path"].read_bytes()
    evidence = json.loads(raw)
    fields(evidence, {"accepted", "policy", "report"}, "published catalogue quality report")
    report = evidence["report"]
    fields(report, {"manifest", "tables", "providers", "metrics", "issues", "sha256", "bytes", "policy"}, "published catalogue report")
    if type(evidence["accepted"]) is not bool or not isinstance(evidence["policy"], dict) or not evidence["policy"]:
        raise ValueError("published quality report requires explicit acceptance and policy")
    if (report["policy"] != evidence["policy"] or report["sha256"] != archive["sha256"]
            or type(report["bytes"]) is not int or report["bytes"] != archive["bytes"]):
        raise ValueError("published quality report does not identify its archive and policy")
    if (not isinstance(report["issues"], list) or any(not isinstance(issue, str) or not issue.strip() for issue in report["issues"])
            or evidence["accepted"] != (not report["issues"])):
        raise ValueError("published acceptance and quality issues are inconsistent")
    for key in ("tables", "providers", "metrics"):
        counts(report[key], key)
    manifest = report["manifest"]
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] <= 0 or not isinstance(manifest.get("taken_at"), str)
            or not manifest["taken_at"].strip() or manifest.get("tables") != report["tables"]
            or set(report["tables"]) != set(TABLE_KEYS)
            or sum(report["providers"].values()) != report["tables"]["opendata_catalog"]):
        raise ValueError("published catalogue manifest and measured table/provider counts disagree")
    with tarfile.open(archive["path"], "r:gz") as source:
        members = source.getmembers()
        expected = {"manifest.json", *(f"{table}.jsonl" for table in TABLE_KEYS)}
        if (len(members) != len(expected) or {member.name for member in members} != expected
                or any(not member.isfile() for member in members)):
            raise ValueError("published archive must contain exactly the declared seven regular tables and manifest")
        if json.load(source.extractfile("manifest.json")) != manifest:
            raise ValueError("published archive manifest differs from its quality report")
    if verify_remote:
        for artifact in (archive, quality):
            verify_download(artifact["url"], artifact["sha256"], artifact["bytes"],
                            remaining(config, config["hub"]["timeout_seconds"]), deadline=config.get("run_deadline"))
    return {"archive": archive, "quality_report": quality, "quality_bytes": raw, "evidence": evidence}


def current_status(evidence, policy):
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    observed = evidence["evidence"]["report"]["manifest"]["schema_version"]
    return {
        "schema_version": 1,
        "evidence_mode": "published_report",
        "archive": {key: value for key, value in evidence["archive"].items() if key != "path"},
        "quality_report": {key: value for key, value in evidence["quality_report"].items() if key != "path"},
        "current_policy": policy,
        "current_policy_sha256": hashlib.sha256(raw).hexdigest(),
        "required_snapshot_schema": SCHEMA_VERSION,
        "observed_snapshot_schema": observed,
        "current_quality_evaluation": "not_performed",
        "admitted": False,
        "reason": "snapshot_schema_mismatch" if observed != SCHEMA_VERSION else "current_quality_not_evaluated",
    }
