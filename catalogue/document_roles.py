"""Independently validate native lifecycle authority in document archives."""

import re
from copy import deepcopy
from datetime import datetime
from typing import Any


def validate_rule(rule):
    if not isinstance(rule, dict):
        raise TypeError("document source role requires an explicit mapping")
    if rule.get("mode") == "catalogue_fields":
        if set(rule) != {"mode"}:
            raise ValueError("catalogue field role has undeclared configuration")
    elif rule.get("mode") == "lifecycle_registry":
        if set(rule) != {"mode", "inventory", "source_role"} or any(
            not isinstance(value, str) or not value or value != value.strip() for value in rule.values()
        ):
            raise ValueError("native registry role requires exact inventory and source-role identities")
    else:
        raise ValueError("document source role mode is not declared")


def _validate_receipt(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"normalized_sha256", "datasets"}:
        raise ValueError("invalid catalogue inventory receipt")
    if not isinstance(value["normalized_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", value["normalized_sha256"],
    ):
        raise ValueError("invalid normalized catalogue inventory digest")
    if type(value["datasets"]) is not int or value["datasets"] <= 0:
        raise ValueError("invalid complete catalogue inventory size")

def _validate_time(value: Any) -> datetime:
    if not isinstance(value, str) or datetime.fromisoformat(value).tzinfo is None:
        raise ValueError("catalogue reconciliation time requires an explicit timezone")
    return datetime.fromisoformat(value)

def validate_evidence(value: Any) -> None:
    if not isinstance(value, dict):
        raise TypeError("catalogue inventory evidence must be an object")
    for name in value:
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError("catalogue inventory identities must be trimmed strings")
    authorities = 0
    for name, membership in value.items():
        if not isinstance(membership, dict) or set(membership) != {
            "present", "role", "reconciled_at", "inventory", "record",
        }:
            raise ValueError("invalid stored catalogue membership")
        if type(membership["present"]) is not bool or membership["role"] not in ("discovery", "lifecycle"):
            raise ValueError("stored catalogue membership has an invalid presence or role")
        authorities += membership["role"] == "lifecycle"
        if authorities > 1:
            raise ValueError("catalogue evidence declares multiple lifecycle authorities")
        checked = _validate_time(membership["reconciled_at"])
        _validate_receipt(membership["inventory"])
        record = membership["record"]
        if record is None and not membership["present"]:
            continue
        if not isinstance(record, dict) or set(record) != {
            "title", "fields", "reconciled_at", "inventory",
        }:
            raise ValueError("present catalogue membership requires its source record")
        recorded = _validate_time(record["reconciled_at"])
        if recorded > checked:
            raise ValueError("catalogue source record is newer than its membership")
        if membership["present"] and (recorded != checked or record["inventory"] != membership["inventory"]):
            raise ValueError("present catalogue source record must match its inventory receipt")
        _validate_receipt(record["inventory"])
        if not isinstance(record["fields"], dict):
            raise TypeError("invalid stored catalogue source fields")
        for flag in ("active", "served", "retired"):
            if type(record["fields"].get(flag)) is not bool:
                raise ValueError(f"stored catalogue source requires boolean {flag}")

def validate_lifecycle(row: dict, memberships: dict) -> None:
    for evidence in memberships.values():
        if evidence["role"] != "lifecycle":
            continue
        flags = evidence["record"]["fields"] if evidence["present"] else {
            "active": False, "served": False, "retired": True,
        }
        for flag in ("active", "served", "retired"):
            if row.get(flag) is not flags[flag]:
                raise ValueError(f"catalogue {flag} contradicts its lifecycle inventory evidence")

def validate_source_observation(observation: dict) -> None:
    if not isinstance(observation, dict) or set(observation) != {"url", "sha256", "bytes", "observed_at", "datasets"}:
        raise ValueError("registry observation requires URL, SHA-256, byte count, source clock and dataset count")
    if not isinstance(observation["url"], str) or not observation["url"].startswith("https://"):
        raise ValueError("registry observation requires its HTTPS source URL")
    if not isinstance(observation["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", observation["sha256"]):
        raise ValueError("registry observation requires its exact body SHA-256")
    if any(type(observation[field]) is not int or observation[field] <= 0 for field in ("bytes", "datasets")):
        raise ValueError("registry observation requires positive byte and dataset counts")
    if not isinstance(observation["observed_at"], str) or datetime.fromisoformat(observation["observed_at"]).tzinfo is None:
        raise ValueError("registry observation requires an explicit source clock with timezone")

def resolve(row: dict, rule: dict, provider: dict) -> tuple[dict, dict | None]:
    if rule["mode"] == "catalogue_fields":
        return row, None
    memberships = row.get("inventory_memberships")
    if memberships is None:
        raise ValueError("registry document preparation requires explicit inventory memberships")
    validate_evidence(memberships)
    held_roles = [source for source in row.get("sources", [])
                  if isinstance(source, dict) and source.get("role") == rule["source_role"]]
    member = memberships.get(rule["inventory"])
    if member is None:
        if row["served"] is False or any(source.get("queryable") is False for source in held_roles):
            raise ValueError("nonqueryable document role requires a qualified lifecycle membership")
        return row, None
    if member["role"] != "lifecycle" or not member["present"]:
        raise ValueError("registry document authority requires a present lifecycle membership")
    validate_lifecycle(row, memberships)
    record = member["record"]
    fields = record["fields"]
    sources = [source for source in fields.get("sources", [])
               if isinstance(source, dict) and source.get("role") == rule["source_role"]]
    if not sources and row["served"] is True:
        return row, None
    if len(sources) != 1 or held_roles != sources:
        raise ValueError("registry document requires one unambiguous persisted source role")
    source = sources[0]
    queryable = source.get("queryable")
    if type(queryable) is not bool:
        raise ValueError("registry document source requires an explicit queryable boolean")
    excluded = provider["extra"]["registry_non_queryable_structures"]
    if queryable is (source.get("reference") in excluded):
        raise ValueError("registry queryability contradicts the declared provider contract")
    if queryable:
        return row, None
    if row["served"] is not False:
        raise ValueError("metadata-only document cannot be eligible for observation acquisition")
    evidence = source.get("registry")
    if not isinstance(evidence, dict) or set(evidence) != {"observation", "native"}:
        raise ValueError("metadata-only document requires qualified native registry evidence")
    observation, native = evidence["observation"], evidence["native"]
    validate_source_observation(observation)
    expected_url = f"{provider['base_url']}/dataflow/{provider['extra']['agency']}"
    if observation["url"] != expected_url or observation["datasets"] != member["inventory"]["datasets"]:
        raise ValueError("registry document must bind its complete native inventory receipt")
    if not isinstance(native, dict) or any(native.get(key) != row.get(column) for key, column in (
        ("agency", "agency"), ("df_id", "dataset_id"), ("version", "version"),
    )):
        raise ValueError("registry document source has a different native dataflow identity")
    if any(not isinstance(native.get(field), str) or not native[field] or native[field] != native[field].strip()
           for field in ("agency", "df_id", "version")):
        raise ValueError("registry document requires complete native dataflow identity")
    if source["reference"] != native.get("structure_reference"):
        raise ValueError("registry document structure reference differs from its native evidence")
    for field in ("agency", "version", "names", "descriptions", "keywords", "structure_id"):
        if fields.get(field) != native.get(field):
            raise ValueError(f"registry document {field} differs from its native evidence")
    if fields.get("seen_registry_at") != observation["observed_at"]:
        raise ValueError("registry document source clock differs from its qualified observation")
    if datetime.fromisoformat(observation["observed_at"]) > datetime.fromisoformat(record["reconciled_at"]):
        raise ValueError("registry document observation cannot follow its reconciliation")
    annotations = native.get("annotations")
    if not isinstance(annotations, list):
        raise TypeError("native registry annotations must be an ordered collection")
    for annotation in annotations:
        if not isinstance(annotation, dict) or set(annotation) != {"id", "type", "title", "url", "texts"}:
            raise ValueError("native registry annotation has invalid fields")
        if any(annotation[field] is not None and not isinstance(annotation[field], str)
               for field in ("id", "type", "title", "url")) or not isinstance(annotation["texts"], list):
            raise ValueError("native registry annotation has invalid values")
        for value in annotation["texts"]:
            if not isinstance(value, dict) or set(value) != {"language", "text"} or any(
                item is not None and not isinstance(item, str) for item in value.values()
            ):
                raise ValueError("native registry annotation text requires its declared language")
    effective = deepcopy(row)
    effective.update({field: deepcopy(native[field]) for field in (
        "agency", "version", "names", "descriptions", "keywords", "structure_id", "report_key",
    )})
    effective.update(
        title=native["names"].get(provider["extra"]["catalog_language"]),
        title_en=native["names"].get("en"), description=None, category_path=None,
        category_paths={}, period_start=None, period_end=None, freshness=None,
        filters=[], caveat=None, document_role={"kind": "metadata_only", "annotations": deepcopy(annotations)},
    )
    return effective, {"kind": "metadata_only", "inventory": rule["inventory"], "membership": deepcopy(member)}
