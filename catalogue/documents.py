"""Verify the discovery archive's explicit document authority contract."""

import hashlib
import json
from collections import Counter

from .config import fields


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    ).encode()).hexdigest()


def inspect_contract(manifest, policy):
    if policy["maximum_missing_documents"] != 0:
        raise ValueError("exact document membership requires maximum_missing_documents=0")
    contract = manifest.get("document_contract")
    fields(contract, {"schema_version", "eligibility_fields", "providers", "searches", "definitions"}, "document contract")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise ValueError("document contract schema_version must be 1")
    sha256 = digest(contract)
    if manifest.get("document_contract_sha256") != sha256 or policy["document_contract_sha256"] != sha256:
        raise ValueError("document contract digest differs from the explicitly configured release policy")
    if contract["eligibility_fields"] != policy["document_fields"]:
        raise ValueError("document eligibility differs from the configured release policy")
    if set(contract["providers"]) != set(policy["providers"]):
        raise ValueError("document providers differ from the configured release policy")
    languages = set()
    for provider, projections in contract["providers"].items():
        if set(projections) != set(policy["providers"][provider]["languages"]):
            raise ValueError(f"document languages for {provider!r} differ from the configured release policy")
        if any(authority not in {"native_metadata", "workspace_definition"} for authority in projections.values()):
            raise ValueError("document authority must be native_metadata or workspace_definition")
        languages.update(projections)
    if set(contract["searches"]) != set(policy["query_languages"]):
        raise ValueError("document query languages differ from the configured release policy")
    for language, stores in contract["searches"].items():
        if not isinstance(stores, list) or len(stores) != len(set(stores)) or set(stores) != languages:
            raise ValueError(f"query language {language!r} does not cover every declared document store")
    return contract


def inspect_membership(catalogue, documents, contract, manifest):
    metrics = Counter()
    issues = []
    expected = {
        (provider, dataset, language)
        for (provider, dataset), row in catalogue.items()
        if all(row[field] is True for field in contract["eligibility_fields"])
        for language in contract["providers"][provider]
    }
    held = set(documents)
    metrics["missing_documents"] = len(expected - held)
    metrics["undeclared_documents"] = len(held - expected)
    sha256 = digest(contract)
    for identity, document in documents.items():
        if identity not in expected:
            continue
        provider, dataset, language = identity
        row = catalogue[(provider, dataset)]
        authority = contract["providers"][provider][language]
        if authority == "workspace_definition":
            source = contract["definitions"].get(language, {}).get(dataset)
        else:
            names = row.get("names")
            title = names.get(language) if isinstance(names, dict) else None
            source = {"title": title, "metadata": {
                field: row.get(field) for field in (
                    "names", "descriptions", "category_paths", "keywords", "caveat",
                    "filters", "sources", "period_start", "period_end", "freshness",
                )
            }}
        if not isinstance(source, dict) or not isinstance(source.get("title"), str) or not source["title"].strip():
            metrics["invalid_document_projections"] += 1
            continue
        text = document["text"]
        text_sha256 = hashlib.sha256(text.encode()).hexdigest()
        proof = {
            "contract_sha256": sha256, "authority": authority, "source_language": language,
            "source_sha256": digest(source), "text_sha256": text_sha256,
        }
        if (
            text.split("\n\n", 1)[0].partition("\n")[2] != source["title"]
            or document.get("text_hash") != text_sha256
            or document.get("projection") != proof
        ):
            metrics["invalid_document_projections"] += 1
    for key in ("undeclared_documents", "invalid_document_projections"):
        if metrics[key]:
            issues.append(f"{key}: {metrics[key]} violates exact document membership")
    receipt = {"documents": len(held), "missing": 0, "undeclared": 0, "contract_sha256": sha256}
    if manifest.get("document_membership") != receipt:
        issues.append("document membership receipt differs from the inspected archive")
    return metrics, issues
