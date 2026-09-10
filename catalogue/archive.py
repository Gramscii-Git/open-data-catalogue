"""Inspect the seven-table snapshot without extracting archive paths."""

import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path

from .documents import inspect_contract, inspect_membership

TABLE_KEYS = {
    "opendata_catalog": ("provider", "dataset_id"),
    "opendata_structures": ("provider", "dataset_id"),
    "opendata_structure_dims": ("provider", "structure_id", "dimension_id"),
    "opendata_terms": ("provider", "language", "scope", "code"),
    "opendata_labels": ("provider", "dataset_id", "language"),
    "opendata_meta_reports": ("provider", "report_key"),
    "opendata_documents": ("provider", "dataset_id", "language"),
}


class QualityError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("catalogue release rejected: " + "; ".join(report["issues"]))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_archive(path: Path, policy: dict) -> dict:
    counts = {}
    metrics = Counter()
    catalog = {}
    structures = set()
    documents = {}
    terms = set()
    dimensions = set()
    references = set()
    related_datasets = set()
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
                "archive must contain exactly the seven JSONL tables and manifest.json as regular files"
            )
        manifest = json.load(archive.extractfile("manifest.json"))
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 2
        ):
            raise ValueError("snapshot schema_version must be 2 with explicit document provenance")
        document_contract = inspect_contract(manifest, policy)
        if not isinstance(manifest.get("taken_at"), str) or not manifest["taken_at"]:
            raise ValueError("snapshot taken_at is required")
        if not isinstance(manifest.get("tables"), dict) or set(
            manifest["tables"]
        ) != set(TABLE_KEYS):
            raise ValueError("manifest must count every snapshot table")
        for table, keys in TABLE_KEYS.items():
            seen = set()
            count = 0
            for line in archive.extractfile(f"{table}.jsonl"):
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
                provider = row["provider"]
                if provider not in policy["providers"]:
                    raise ValueError(
                        f"{table}: provider {provider!r} has no release policy"
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
                    catalog[identity] = row
                    providers[provider] += 1
                    metrics["missing_licences"] += (
                        not isinstance(row.get("licence"), str)
                        or not row["licence"].strip()
                    )
                elif table == "opendata_structures":
                    if "error" not in row or "harvested_at" not in row:
                        raise ValueError("structure must declare its harvest state")
                    metrics["structure_errors"] += row["error"] is not None
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
            counts[table] = count
            declared = manifest["tables"][table]
            if type(declared) is not int or declared != count:
                raise ValueError(
                    f"{table}: manifest count {declared!r} does not match {count}"
                )
    if related_datasets - catalog.keys():
        issues.append(
            f"{len(related_datasets - catalog.keys())} dataset references have no catalogue row"
        )
    if references - terms:
        issues.append(
            f"{len(references - terms)} dimension vocabulary references have no terms"
        )
    for provider, contract in policy["providers"].items():
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
    if len(catalog) < policy["minimum_datasets"]:
        issues.append(
            f"dataset count {len(catalog)} is below {policy['minimum_datasets']}"
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
    if issues:
        raise QualityError(report)
    return report
