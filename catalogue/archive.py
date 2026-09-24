"""Inspect the complete discovery snapshot without extracting archive paths."""

import base64
import binascii
import hashlib
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

from .documents import inspect_contract, inspect_membership
from .structure_errors import declared_permanent

SCHEMA_VERSION = 4

TABLE_KEYS = {
    "opendata_catalog": ("provider", "dataset_id"),
    "opendata_structures": ("provider", "dataset_id"),
    "opendata_structure_dims": ("provider", "structure_id", "dimension_id"),
    "opendata_terms": ("provider", "language", "scope", "code"),
    "opendata_labels": ("provider", "dataset_id", "language"),
    "opendata_meta_reports": ("provider", "report_key"),
    "opendata_documents": ("provider", "dataset_id", "language"),
    "opendata_native_objects": ("sha256",),
    "opendata_native_bindings": ("provider", "dataset_id"),
    "opendata_native_exclusions": ("provider", "reference"),
}


class QualityError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("catalogue release rejected: " + "; ".join(report["issues"]))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_archive(
    path: Path,
    policy: dict,
    *,
    required_providers: set[str] | None = None,
    minimum_datasets: int | None = None,
) -> dict:
    selected_providers = (
        set(policy["providers"])
        if required_providers is None
        else set(required_providers)
    )
    if not selected_providers or not selected_providers <= set(policy["providers"]):
        raise ValueError("required providers must be a nonempty subset of the release policy")
    required_minimum = policy["minimum_datasets"] if minimum_datasets is None else minimum_datasets
    if type(required_minimum) is not int or required_minimum < 0:
        raise ValueError("minimum datasets must be a non-negative integer")
    counts = {}
    metrics = Counter()
    catalog = {}
    structures = set()
    documents = {}
    terms = set()
    dimensions = set()
    references = set()
    related_datasets = set()
    native_objects = set()
    native_bindings = {}
    providers = Counter()
    issues = []
    source_tables = {name: [] for name in ("opendata_structures", "opendata_terms", "opendata_structure_dims", "opendata_meta_reports")}
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        expected = {f"{table}.jsonl" for table in TABLE_KEYS} | {"manifest.json"}
        if (
            len(members) != len(expected)
            or {member.name for member in members} != expected
            or any(not member.isfile() for member in members)
        ):
            raise ValueError(
                "archive must contain exactly the declared JSONL tables and manifest.json as regular files"
            )
        manifest = json.load(archive.extractfile("manifest.json"))
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != SCHEMA_VERSION
        ):
            raise ValueError("snapshot schema_version must be 4 with native evidence and explicit document provenance")
        document_contract = inspect_contract(manifest, policy)
        if not isinstance(manifest.get("taken_at"), str) or not manifest["taken_at"]:
            raise ValueError("snapshot taken_at is required")
        if not isinstance(manifest.get("tables"), dict) or set(
            manifest["tables"]
        ) != set(TABLE_KEYS):
            raise ValueError("manifest must count every snapshot table")
        jsonl_members = {f"{table}.jsonl" for table in TABLE_KEYS}
        if not isinstance(manifest.get("members"), dict) or set(manifest["members"]) != jsonl_members:
            raise ValueError("manifest must identify every snapshot table member")
        for table, keys in TABLE_KEYS.items():
            seen = set()
            count = 0
            member_name = f"{table}.jsonl"
            checksum = hashlib.sha256()
            size = 0
            for line in archive.extractfile(member_name):
                checksum.update(line)
                size += len(line)
                row = json.loads(line)
                if not isinstance(row, dict) or any(
                    not isinstance(row.get(key), str) for key in keys
                ):
                    raise ValueError(f"{table}: invalid row identity")
                identity = tuple(row[key] for key in keys)
                if identity in seen:
                    raise ValueError(f"{table}: duplicate key {identity!r}")
                seen.add(identity)
                count += 1
                provider = row.get("provider")
                if provider is not None:
                    if provider not in policy["providers"]:
                        raise ValueError(
                            f"{table}: provider {provider!r} has no release policy"
                        )
                    if provider not in selected_providers:
                        raise ValueError(
                            f"{table}: provider {provider!r} is outside the declared release scope"
                        )
                if table in source_tables and (table != "opendata_terms" or row["language"] in document_contract["localization_languages"][provider]):
                    source_tables[table].append(row)
                if "dataset_id" in row:
                    related_datasets.add((provider, row["dataset_id"]))
                if table == "opendata_catalog":
                    for field in (
                        *policy["structure_fields"],
                        *policy["document_fields"],
                    ):
                        if (
                            field not in row
                            or row[field] is not None
                            and type(row[field]) is not bool
                        ):
                            raise ValueError(
                                f"catalogue field {field!r} must be boolean or null"
                            )
                    if type(row.get("retired")) is not bool:
                        raise ValueError("catalogue field 'retired' must be boolean")
                    if row["retired"]:
                        raise ValueError(
                            f"catalogue row {identity!r} is retired; a published archive holds current datasets"
                        )
                    catalog[identity] = row
                    providers[provider] += 1
                    # A licence governs data SDG serves; an unserved dataset is never given an inferred one.
                    metrics["missing_licences"] += all(
                        row[field] is True for field in policy["structure_fields"]
                    ) and (not isinstance(row.get("licence"), str) or not row["licence"].strip())
                elif table == "opendata_structures":
                    if "error" not in row or "harvested_at" not in row:
                        raise ValueError("structure must declare its harvest state")
                    permanent = isinstance(row["error"], str) and declared_permanent(
                        document_contract["rendering"]["providers"][provider], row["error"]
                    )
                    metrics["permanent_structure_errors"] += permanent
                    metrics["structure_errors"] += row["error"] is not None and not permanent
                    if row["harvested_at"] is not None:
                        structures.add(identity)
                elif table == "opendata_documents":
                    if not isinstance(row.get("text"), str) or not row["text"].strip():
                        raise ValueError(f"document {identity!r} has no text")
                    documents[identity] = row
                elif table == "opendata_terms":
                    prefix, separator, code = row["scope"].partition(":")
                    metrics["unscoped_terms"] += (
                        not separator or not code or prefix not in policy["term_scopes"]
                    )
                    terms.add((provider, row["scope"]))
                elif table == "opendata_structure_dims":
                    dimensions.add(provider)
                    for name in ("concept_scope", "codelist_scope"):
                        if not isinstance(row.get(name), str):
                            raise TypeError(
                                f"dimension {identity!r} must declare {name}"
                            )
                        if row[name]:
                            references.add((provider, row[name]))
                elif table == "opendata_native_objects":
                    try:
                        body = base64.b64decode(row.get("body", ""), validate=True)
                    except (binascii.Error, ValueError) as error:
                        raise ValueError(f"native object {identity!r} has invalid base64 content") from error
                    if hashlib.sha256(body).hexdigest() != row["sha256"]:
                        raise ValueError(f"native object {identity!r} content differs from its digest")
                    native_objects.add(row["sha256"])
                elif table == "opendata_native_bindings":
                    for name in ("projection_sha256", "graph_sha256", "flow_sha256"):
                        value = row.get(name)
                        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                            raise ValueError(f"native binding {identity!r} has invalid {name}")
                    receipts = row.get("receipts")
                    if not isinstance(receipts, list) or not receipts:
                        raise ValueError(f"native binding {identity!r} has no receipts")
                    for receipt in receipts:
                        if (
                            not isinstance(receipt, dict)
                            or not isinstance(receipt.get("sha256"), str)
                            or not re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"])
                            or type(receipt.get("bytes")) is not int
                            or receipt["bytes"] <= 0
                        ):
                            raise ValueError(f"native binding {identity!r} has an invalid source receipt")
                    native_bindings[identity] = row
            counts[table] = count
            declared = manifest["tables"][table]
            if type(declared) is not int or declared != count:
                raise ValueError(
                    f"{table}: manifest count {declared!r} does not match {count}"
                )
            declared_member = manifest["members"][member_name]
            if declared_member != {"sha256": checksum.hexdigest(), "bytes": size}:
                raise ValueError(f"{member_name}: manifest member receipt differs from its content")
    if related_datasets - catalog.keys():
        issues.append(
            f"{len(related_datasets - catalog.keys())} dataset references have no catalogue row"
        )
    if references - terms:
        issues.append(
            f"{len(references - terms)} dimension vocabulary references have no terms"
        )
    missing_native_objects = {
        digest
        for binding in native_bindings.values()
        for digest in (
            binding["graph_sha256"], binding["flow_sha256"],
            *(receipt["sha256"] for receipt in binding["receipts"]),
        )
        if digest not in native_objects
    }
    if missing_native_objects:
        issues.append(f"{len(missing_native_objects)} native binding objects are missing")
    for provider in sorted(selected_providers):
        contract = policy["providers"][provider]
        if not providers[provider]:
            issues.append(f"required provider {provider!r} has no datasets")
        if contract["vocabulary"] and (
            provider not in dimensions or not any(key[0] == provider for key in terms)
        ):
            issues.append(
                f"provider {provider!r} lacks structure dimensions or vocabulary"
            )
    for (provider, dataset), row in catalog.items():
        if all(row[field] is True for field in policy["structure_fields"]):
            metrics["missing_structures"] += (provider, dataset) not in structures
    document_metrics, document_issues = inspect_membership(catalog, documents, document_contract, manifest, source_tables)
    metrics.update(document_metrics)
    issues.extend(document_issues)
    if len(catalog) < required_minimum:
        issues.append(
            f"dataset count {len(catalog)} is below {required_minimum}"
        )
    for name in (
        "structure_errors",
        "missing_structures",
        "missing_licences",
        "missing_documents",
        "unscoped_terms",
    ):
        value = metrics[name]
        maximum = policy[f"maximum_{name}"]
        if value > maximum:
            issues.append(f"{name}: {value} exceeds permitted {maximum}")
    report = {
        "manifest": manifest,
        "tables": counts,
        "providers": dict(providers),
        "metrics": dict(metrics),
        "issues": issues,
        "sha256": digest(path),
        "bytes": path.stat().st_size,
        "policy": policy,
    }
    if required_providers is not None or minimum_datasets is not None:
        report["scope"] = {
            "providers": sorted(selected_providers),
            "minimum_datasets": required_minimum,
        }
    if issues:
        raise QualityError(report)
    return report
