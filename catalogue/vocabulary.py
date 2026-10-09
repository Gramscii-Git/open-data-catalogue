"""Bind native vocabulary projections to their archived layer structures."""

import math
from urllib.parse import quote, urlencode, urlsplit

# The source driver whose layers each native strategy binds its scopes to.
NATIVE = {"arcgis_structure": "arcgis", "wfs_structure": "wfs"}


class Vocabulary:
    def __init__(self, policy, contract):
        self.policy = policy
        self.providers = contract["rendering"]["providers"]
        self.scopes = set()
        self.terms = {}
        self.dimensions = {}
        self.seen_terms = set()
        self.seen_dimensions = set()
        for provider, declaration in policy["providers"].items():
            strategy = declaration["vocabulary_scopes"]
            if strategy not in {"prefixed", *NATIVE}:
                raise ValueError(f"{provider}: unknown vocabulary scope strategy")
            if self.native(provider):
                source = self.providers[provider]
                origin = urlsplit(source.get("base_url", ""))
                language = source.get("extra", {}).get("catalog_language")
                if (source.get("driver") != NATIVE[strategy] or origin.scheme != "https" or not origin.hostname
                        or origin.username or origin.password or origin.query or origin.fragment
                        or not isinstance(language, str) or not language
                        or not declaration["vocabulary"]):
                    raise ValueError(f"{provider}: native vocabulary requires its {NATIVE[strategy]} source and language")
                service = source["extra"].get("wfs_policy", {}).get("service") if strategy == "wfs_structure" else None
                if strategy == "wfs_structure" and (
                        not isinstance(service, dict) or not isinstance(service.get("path"), str)
                        or any(part in {"", ".", ".."} for part in service["path"].split("/"))
                        or not isinstance(service.get("version"), str) or not service["version"]):
                    raise ValueError(f"{provider}: native vocabulary requires its WFS service path and version")

    def native(self, provider):
        return self.policy["providers"][provider]["vocabulary_scopes"] in NATIVE

    def layer(self, provider, dataset):
        """The URL a layer's structure is described at, written as the provider's source driver writes it."""
        source = self.providers[provider]
        base = source["base_url"].rstrip("/") + "/"
        if self.policy["providers"][provider]["vocabulary_scopes"] == "arcgis_structure":
            return base + quote(dataset, safe="/")
        service = source["extra"]["wfs_policy"]["service"]
        query = {"service": "WFS", "version": service["version"], "request": "DescribeFeatureType", "typeNames": dataset}
        return base + quote(service["path"], safe="/") + "?" + urlencode(query, safe=":,")

    def add_structure(self, row, catalog):
        provider = row["provider"]
        if not self.native(provider) or row["error"] is not None or row["harvested_at"] is None:
            return
        source = self.providers[provider]
        reference = self.layer(provider, row["dataset_id"])
        services = catalog.get("sources") if catalog is not None else None
        services = [item for item in services if isinstance(item, dict) and item.get("role") == "service"] if isinstance(services, list) else []
        fields = row.get("dimensions")
        if (row.get("source_reference") != reference or not isinstance(row.get("spatial"), dict)
                or len(services) != 1 or services[0].get("url") != reference
                or not isinstance(fields, list) or not fields):
            raise ValueError(f"{provider}: native vocabulary requires its catalogue layer and spatial fields")
        language = source["extra"]["catalog_language"]
        concepts = reference + "#fields"
        self.scopes.add((provider, concepts))
        for field in fields:
            if (not isinstance(field, dict) or any(not isinstance(field.get(key), str) or not field[key]
                                                  for key in ("id", "name"))):
                raise ValueError(f"{provider}: native vocabulary has invalid field identities")
            identity = (provider, reference, field["id"])
            if identity in self.dimensions:
                raise ValueError(f"{provider}: native vocabulary repeats a layer field")
            classification = field.get("classification")
            scope = reference + "#" + field["id"] if classification is not None else ""
            self.dimensions[identity] = (concepts, field["id"], scope)
            self.terms[(provider, language, concepts, field["id"])] = field["name"]
            if classification is not None:
                self.scopes.add((provider, scope))
                self.add_classification(provider, language, scope, field["id"], classification)

    def add_classification(self, provider, language, scope, field, classification):
        if not isinstance(classification, dict):
            raise TypeError(f"{provider}: native classification must be an object")
        keys, count, values = (classification.get(key) for key in ("fields", "non_null_distinct_count", "values"))
        if (not isinstance(keys, list) or len(keys) not in (1, 2) or keys[0] != field
                or any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys)
                or type(count) is not int or count < 0 or values is not None and not isinstance(values, list)):
            raise ValueError(f"{provider}: native classification has invalid fields or count")
        if values is None:
            return
        codes = set()
        null_seen = False
        for value in values:
            if not isinstance(value, dict) or set(value) != set(keys):
                raise ValueError(f"{provider}: native classification values differ from their fields")
            code = value[keys[0]]
            if code is None:
                if null_seen:
                    raise ValueError(f"{provider}: native classification repeats NULL")
                null_seen = True
                continue
            if type(code) not in (str, int, float) or isinstance(code, float) and not math.isfinite(code):
                raise ValueError(f"{provider}: native classification code is not a finite scalar")
            code = str(code)
            if code in codes:
                raise ValueError(f"{provider}: native classification repeats a code")
            codes.add(code)
            label = value[keys[1]] if len(keys) == 2 else value[keys[0]] if isinstance(value[keys[0]], str) else None
            if label is not None and not isinstance(label, str):
                raise ValueError(f"{provider}: native classification label must be text or null")
            self.terms[(provider, language, scope, code)] = label
        if len(codes) != count:
            raise ValueError(f"{provider}: native classification differs from its non-null count")

    def dimension(self, row):
        identity = (row["provider"], row["structure_id"], row["dimension_id"])
        held = tuple(row.get(key) for key in ("concept_scope", "concept_id", "codelist_scope"))
        if identity not in self.dimensions or held != self.dimensions[identity]:
            raise ValueError(f"native dimension {identity!r} differs from its layer structure")
        self.seen_dimensions.add(identity)

    def term(self, row):
        provider = row["provider"]
        if not self.native(provider):
            prefix, separator, code = row["scope"].partition(":")
            return bool(separator and code and prefix in self.policy["term_scopes"])
        if (provider, row["scope"]) not in self.scopes:
            return False
        identity = (provider, row["language"], row["scope"], row["code"])
        if identity not in self.terms or "name" not in row or row["name"] != self.terms[identity]:
            raise ValueError(f"native term {identity!r} differs from its layer structure")
        self.seen_terms.add(identity)
        return True

    def issues(self):
        issues = []
        for kind, expected, seen in (("terms", self.terms, self.seen_terms), ("dimensions", self.dimensions, self.seen_dimensions)):
            missing = expected.keys() - seen
            if missing:
                issues.append(f"{len(missing)} native vocabulary {kind} are missing from their layer projections")
        return issues
