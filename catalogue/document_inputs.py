"""Reconstruct document source envelopes from the archive's pinned input schema."""

from collections import defaultdict


class Inputs:
    def __init__(self, tables, contract, digest):
        self.contract = contract
        self.digest = digest
        self.structures = {(row["provider"], row["dataset_id"]): row for row in tables["opendata_structures"]}
        self.reports = {(row["provider"], row["report_key"]): row["texts"] for row in tables["opendata_meta_reports"]}
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

    def envelope(self, row, language, authority):
        provider, dataset = row["provider"], row["dataset_id"]
        schema = self.contract["rendering"]["source_fields"]
        held = self.structures.get((provider, dataset))
        structure = {field: held.get(field) for field in schema["structure"]} if held is not None else None
        localization = None
        if structure is not None and language in self.contract["localization_languages"][provider]:
            key = (provider, language)
            if key not in self.localization:
                if not self.terms[key] or not self.dimensions[provider]:
                    raise ValueError(f"{provider}:{language} document localization requires stored terms and structure references")
                self.localization[key] = self.digest({"terms": self.terms[key], "dimensions": self.dimensions[provider]})
            localization = self.localization[key]
        return {
            "authority": authority,
            "catalogue": {"provider": provider, "dataset_id": dataset, "title": row["title"],
                          "fields": {field: row.get(field) for field in schema["catalogue"]} | {
                              "report_texts": self.reports.get((provider, row.get("report_key"))),
                          }},
            "structure": structure,
            "localization_sha256": localization,
            "provider_sha256": self.provider_hashes[provider],
            "words_sha256": self.word_hashes[language],
        }
