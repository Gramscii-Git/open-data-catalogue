"""Reconstruct document source envelopes from the archive's pinned input schema."""

from collections import defaultdict
from dataclasses import dataclass

from .document_roles import resolve


@dataclass(frozen=True)
class Prepared:
    row: dict
    catalogue: dict
    structure: dict | None
    role: dict | None


class Inputs:
    def __init__(self, tables, contract, digest, *, structure_lookup=None):
        self.contract = contract
        self.digest = digest
        structures = {(row["provider"], row["dataset_id"]): row for row in tables["opendata_structures"]}
        self.structure_lookup = structures.get if structure_lookup is None else structure_lookup
        self.reports = {(row["provider"], row["report_key"]): row["texts"] for row in tables["opendata_meta_reports"]}
        # The codes each dataset's document lists in each dimension, fixed by its provider's last build.
        self.codes = defaultdict(dict)
        for row in tables["opendata_document_codes"]:
            self.codes[(row["provider"], row["dataset_id"])][row["dimension_id"]] = list(row["codes"])
        self.terms = defaultdict(list)
        self.dimensions = defaultdict(list)
        schema = contract["rendering"]["source_fields"]
        for row in tables["opendata_terms"]:
            if row["language"] in contract["localization_languages"][row["provider"]]:
                self.terms[(row["provider"], row["language"])].append({field: row[field] for field in schema["terms"]})
        for row in tables["opendata_structure_dims"]:
            self.dimensions[row["provider"]].append({field: row[field] for field in schema["dimensions"]})
        for rows in self.terms.values():
            rows.sort(key=lambda row: (row["scope"], row["code"]))
        for rows in self.dimensions.values():
            rows.sort(key=lambda row: (row["structure_id"], row["dimension_id"]))
        self.localization = {}
        self.provider_hashes = {key: digest(value) for key, value in contract["rendering"]["providers"].items()}
        self.word_hashes = {key: digest(value) for key, value in contract["rendering"]["words"].items()}

    def prepare(self, row):
        provider, dataset = row["provider"], row["dataset_id"]
        effective, role = resolve(row, self.contract["source_roles"][provider], self.contract["rendering"]["providers"][provider])
        schema = self.contract["rendering"]["source_fields"]
        structure = self.structure(row) if role is None else None
        catalogue = {"provider": provider, "dataset_id": dataset, "title": effective["title"],
                     "fields": {field: effective.get(field) for field in schema["catalogue"]} | {
                         "report_texts": self.reports.get((provider, effective.get("report_key"))),
                     }}
        return Prepared(effective, catalogue, structure, role)

    def structure(self, row):
        """The stored structure with the codes its document lists in each dimension, or none when the catalogue says it
        has none or none is stored."""
        if type(row["structure_available"]) is not bool:
            raise ValueError("document structure availability requires an explicit catalogue boolean")
        identity = (row["provider"], row["dataset_id"])
        held = self.structure_lookup(identity) if row["structure_available"] else None
        if held is None:
            return None
        fields = self.contract["rendering"]["source_fields"]["structure"]
        return {field: held.get(field) for field in fields} | {"document_codes": self.codes.get(identity, {})}

    def envelope(self, prepared, language, authority):
        provider = prepared.row["provider"]
        structure = prepared.structure
        localization = None
        if (
            structure is not None
            and structure.get("source_domain") is None
            and language in self.contract["localization_languages"][provider]
        ):
            key = (provider, language)
            if key not in self.localization:
                if not self.terms[key] or not self.dimensions[provider]:
                    raise ValueError(f"{provider}:{language} document localization requires stored terms and structure references")
                self.localization[key] = self.digest({"terms": self.terms[key], "dimensions": self.dimensions[provider]})
            localization = self.localization[key]
        return {
            "authority": authority,
            "catalogue": prepared.catalogue,
            "document_role": prepared.role,
            "structure": structure,
            "localization_sha256": localization,
            "provider_sha256": self.provider_hashes[provider],
            "words_sha256": self.word_hashes[language],
        }
