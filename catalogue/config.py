"""Load explicit deployment settings and release policy."""

import math
import os
from pathlib import Path
from urllib.parse import urlsplit

import tomllib


def fields(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")


def text(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be non-empty, trimmed text")
    return value


def strings(value, name):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return [text(item, name) for item in value]


def load(path: Path) -> dict:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    fields(
        data, {"schema", "deployment", "hub", "quality", "schedule"}, "configuration"
    )
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError("configuration schema must be 1")
    deployment = data["deployment"]
    fields(
        deployment,
        {"harvester", "environment_file", "python", "hf", "build", "readme_template", "patience_seconds"},
        "deployment",
    )
    for key in ("harvester", "environment_file", "python", "build", "readme_template"):
        raw = Path(text(deployment[key], f"deployment.{key}"))
        deployment[key] = Path(os.path.abspath(path.parent / raw)) if key == "python" else (path.parent / raw).resolve()
    deployment["hf"] = strings(deployment["hf"], "deployment.hf")
    patience = deployment["patience_seconds"]
    if (
        type(patience) not in (int, float)
        or not math.isfinite(patience)
        or patience <= 0
    ):
        raise ValueError("deployment.patience_seconds must be positive and finite")
    hub = data["hub"]
    fields(
        hub,
        {
            "endpoint",
            "repository",
            "branch",
            "archive",
            "commit_message",
            "timeout_seconds",
        },
        "hub",
    )
    for key in ("endpoint", "repository", "branch", "archive", "commit_message"):
        text(hub[key], f"hub.{key}")
    endpoint = urlsplit(hub["endpoint"])
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or endpoint.path
    ):
        raise ValueError("hub.endpoint must be a plain HTTPS origin")
    if len(hub["repository"].split("/")) != 2 or any(
        part in ("", ".", "..") for part in hub["repository"].split("/")
    ):
        raise ValueError("hub.repository must contain an owner and repository")
    if Path(hub["archive"]).name != hub["archive"] or not hub["archive"].endswith(
        ".tar.gz"
    ):
        raise ValueError("hub.archive must be a .tar.gz filename")
    timeout = hub["timeout_seconds"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("hub.timeout_seconds must be positive and finite")
    policy = data["quality"]
    limits = {
        "minimum_datasets",
        "maximum_structure_errors",
        "maximum_missing_structures",
        "maximum_missing_licences",
        "maximum_missing_documents",
        "maximum_unscoped_terms",
    }
    fields(
        policy,
        limits | {"structure_fields", "document_fields", "term_scopes", "providers"},
        "quality",
    )
    for key in limits:
        if type(policy[key]) is not int or policy[key] < 0:
            raise ValueError(f"quality.{key} must be a non-negative integer")
    for key in ("structure_fields", "document_fields", "term_scopes"):
        policy[key] = strings(policy[key], f"quality.{key}")
    if not isinstance(policy["providers"], dict) or not policy["providers"]:
        raise ValueError("quality.providers is required")
    for name, provider in policy["providers"].items():
        text(name, "provider identity")
        fields(provider, {"languages", "vocabulary"}, f"provider {name}")
        provider["languages"] = strings(
            provider["languages"], f"provider {name} languages"
        )
        if type(provider["vocabulary"]) is not bool:
            raise ValueError(f"provider {name} vocabulary must be boolean")
    schedule = data["schedule"]
    if not isinstance(schedule, dict) or "action" not in schedule:
        raise ValueError("schedule.action is required")
    actions = {"prepare", "refresh", "publish", "release", "run-update"}
    if schedule["action"] not in actions:
        raise ValueError("schedule.action must be prepare, refresh, publish, release or run-update")
    timing = {"plan", "interval_seconds"} if schedule["action"] == "run-update" else {"weekday", "hour", "minute"}
    fields(
        schedule,
        {"label", "python", "path", "log", "action"} | timing,
        "schedule",
    )
    for key in ("label", "path"):
        text(schedule[key], f"schedule.{key}")
    for key in ("python", "log"):
        configured = path.parent / Path(text(schedule[key], f"schedule.{key}"))
        schedule[key] = Path(os.path.abspath(configured)) if key == "python" else configured.resolve()
    if schedule["action"] == "run-update":
        schedule["plan"] = (path.parent / text(schedule["plan"], "schedule.plan")).resolve(strict=True)
        if type(schedule["interval_seconds"]) is not int or schedule["interval_seconds"] <= 0:
            raise ValueError("schedule.interval_seconds must be a positive integer")
    else:
        for key, upper in (("weekday", 6), ("hour", 23), ("minute", 59)):
            if type(schedule[key]) is not int or not 0 <= schedule[key] <= upper:
                raise ValueError(f"schedule.{key} is outside its valid range")
    return data
