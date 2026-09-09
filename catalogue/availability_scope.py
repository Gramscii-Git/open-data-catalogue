"""Resolve explicit publisher grids from complete upstream JSON inventories."""

import copy
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("scope inventory redirected; verify its declared source URL")


def inventory_spec(spec):
    fields = {"url", "code_field", "code_pattern", "max_bytes", "max_records", "timeout_seconds"}
    if not isinstance(spec, dict) or set(spec) != fields:
        raise ValueError("scope inventory requires its exact source and resource fields")
    for name in ("max_bytes", "max_records", "timeout_seconds"):
        if type(spec[name]) is not int or spec[name] <= 0:
            raise ValueError(f"scope inventory {name} must be a positive integer")
    for name in ("url", "code_field", "code_pattern"):
        if not isinstance(spec[name], str) or not spec[name] or spec[name] != spec[name].strip():
            raise ValueError(f"scope inventory {name} requires trimmed text")
    url = urlsplit(spec["url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError("scope inventory requires a direct HTTPS source URL")
    return re.compile(spec["code_pattern"])


def inventory(spec):
    pattern = inventory_spec(spec)
    with urllib.request.build_opener(NoRedirect()).open(spec["url"], timeout=spec["timeout_seconds"]) as response:
        if response.status != 200:
            raise ValueError("scope inventory did not return HTTP 200")
        body = response.read(spec["max_bytes"] + 1)
        receipt = {"url": response.url, "status": response.status,
                   "observed_at": datetime.now(UTC).isoformat(),
                   "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
    if len(body) > spec["max_bytes"]:
        raise ValueError("scope inventory exceeds its response byte budget")
    rows = json.loads(body)
    if not isinstance(rows, list) or not 0 < len(rows) <= spec["max_records"]:
        raise ValueError("scope inventory requires a complete non-empty bounded array")
    codes = []
    for row in rows:
        code = row.get(spec["code_field"]) if isinstance(row, dict) else None
        if not isinstance(code, str) or pattern.fullmatch(code) is None:
            raise ValueError("scope inventory contains an invalid source code")
        codes.append(code)
    if len(codes) != len(set(codes)):
        raise ValueError("scope inventory contains duplicate source codes")
    return {"source": spec, "receipt": {**receipt, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
            "codes": sorted(codes)}


def resolve(specification):
    if (set(specification) != {"schema_version", "limits", "datasets", "inventories"}
            or specification["schema_version"] != 2 or not isinstance(specification["inventories"], dict)):
        raise ValueError("publisher scope requires schema version 2 and explicit inventories")
    resolved = copy.deepcopy(specification)
    declarations = resolved.pop("inventories")
    resolved["schema_version"] = 1
    references = []
    for dataset in resolved["datasets"]:
        for argument, values in dataset["varying"].items():
            if isinstance(values, list):
                continue
            if not isinstance(values, dict) or set(values) != {"inventory"} or values["inventory"] not in declarations:
                raise ValueError("varying grid must name a declared source inventory or explicit values")
            references.append({"provider": dataset["provider"], "dataset_id": dataset["dataset_id"],
                               "argument": argument, "inventory": values["inventory"]})
    if {ref["inventory"] for ref in references} != set(declarations):
        raise ValueError("every declared source inventory must be used by the scope")
    inventories = {name: inventory(declaration) for name, declaration in declarations.items()}
    for dataset in resolved["datasets"]:
        for argument, values in dataset["varying"].items():
            if isinstance(values, dict):
                dataset["varying"][argument] = inventories[values["inventory"]]["codes"]
    evidence = {"schema_version": 1, "inventories": inventories, "bindings": references}
    verify_inventory_scope(resolved, evidence)
    return resolved, evidence


def verify_inventory_scope(specification, evidence):
    if (not isinstance(evidence, dict) or set(evidence) != {"schema_version", "inventories", "bindings"}
            or evidence["schema_version"] != 1 or not isinstance(evidence["inventories"], dict)
            or not isinstance(evidence["bindings"], list)):
        raise ValueError("scope inventory evidence has an invalid schema")
    for source in evidence["inventories"].values():
        if not isinstance(source, dict) or set(source) != {"source", "receipt", "codes"}:
            raise ValueError("scope inventory evidence requires source, receipt and codes")
        pattern = inventory_spec(source["source"])
        codes, receipt = source["codes"], source["receipt"]
        if (not isinstance(codes, list) or not 0 < len(codes) <= source["source"]["max_records"]
                or any(not isinstance(code, str) or pattern.fullmatch(code) is None for code in codes)
                or codes != sorted(set(codes))):
            raise ValueError("scope inventory evidence requires distinct sorted source codes")
        if (not isinstance(receipt, dict)
                or set(receipt) != {"url", "status", "observed_at", "etag", "last_modified", "bytes", "sha256"}
                or receipt["url"] != source["source"]["url"] or receipt["status"] != 200
                or type(receipt["bytes"]) is not int or not 0 < receipt["bytes"] <= source["source"]["max_bytes"]
                or not isinstance(receipt["sha256"], str) or re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"]) is None):
            raise ValueError("scope inventory receipt disagrees with its source contract")
        observed = datetime.fromisoformat(receipt["observed_at"])
        if observed.tzinfo is None:
            raise ValueError("scope inventory receipt requires a timezone-aware observation time")
    datasets = {(row["provider"], row["dataset_id"]): row for row in specification["datasets"]}
    bindings = set()
    used = set()
    for binding in evidence["bindings"]:
        if (not isinstance(binding, dict) or set(binding) != {"provider", "dataset_id", "argument", "inventory"}
                or binding["inventory"] not in evidence["inventories"]):
            raise ValueError("scope inventory binding must name a declared inventory")
        identity = binding["provider"], binding["dataset_id"], binding["argument"]
        if identity in bindings:
            raise ValueError("scope inventory contains duplicate bindings")
        bindings.add(identity)
        used.add(binding["inventory"])
        source = evidence["inventories"][binding["inventory"]]
        codes = source["codes"]
        if identity[:2] not in datasets or identity[2] not in datasets[identity[:2]]["varying"]:
            raise ValueError("scope inventory binding must identify a declared request argument")
        values = datasets[identity[:2]]["varying"][identity[2]]
        if values != codes:
            raise ValueError("built scope does not cover its complete source inventory")
    if used != set(evidence["inventories"]):
        raise ValueError("every inventory receipt must bind a built source scope")
