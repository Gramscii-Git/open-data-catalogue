"""Validate source-bound ArcGIS and WFS vocabulary in complete release archives."""

import copy
import tempfile
import unittest
from pathlib import Path

from test_release import DOCUMENT_CONTRACT, ROOT, rows, write_archive

from catalogue.archive import QualityError, inspect_archive
from catalogue.config import load
from catalogue.document_inputs import Inputs
from catalogue.documents import digest


class NativeVocabulary(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = Path(self.temporary.name) / "snapshot.tar.gz"
        self.policy = load(ROOT / "publisher.example.toml")["quality"]
        self.policy.update(minimum_datasets=1, providers={"sample": {
            "languages": ["en"], "vocabulary": True, "vocabulary_scopes": "arcgis_structure",
        }})
        self.contract = copy.deepcopy(DOCUMENT_CONTRACT)
        self.driver = "arcgis"
        self.base = "https://source.example/arcgis/rest/services"
        self.dataset = "Plan A/MapServer/2"
        self.reference = self.base + "/Plan%20A/MapServer/2"
        self.other = self.base + "/Plan%20A/MapServer/3"
        self.contract["rendering"]["providers"]["sample"].update(
            driver="arcgis", base_url=self.base, extra={"catalog_language": "en"},
        )
        self.contract["rendering"]["source_fields"]["structure"].append("spatial")

    def data(self):
        data = rows(self.contract)
        catalog = data["opendata_catalog"][0]
        catalog.update(dataset_id=self.dataset, sources=[{"role": "service", "url": self.reference}])
        data["opendata_structures"][0].update(dataset_id=self.dataset, source_reference=self.reference,
                                             spatial={"geometry_type": "esriGeometryPolygon"}, dimensions=[
            {"id": "TYPE", "name": "Type", "classification": {
                "fields": ["TYPE", "LABEL"], "non_null_distinct_count": 2,
                "values": [{"TYPE": None, "LABEL": None}, {"TYPE": " ", "LABEL": "Native blank"},
                           {"TYPE": "A", "LABEL": "Area A"}],
            }},
            {"id": "ONLY_NULL", "name": "Only null", "classification": {
                "fields": ["ONLY_NULL"], "non_null_distinct_count": 0, "values": [{"ONLY_NULL": None}],
            }},
            {"id": "UNENUMERATED", "name": "Counted domain", "classification": {
                "fields": ["UNENUMERATED"], "non_null_distinct_count": 4000, "values": None,
            }},
            {"id": "OBJECTID", "name": "Object ID"},
        ])
        data["opendata_structure_dims"] = [{
            "provider": "sample", "structure_id": self.reference, "dimension_id": field["id"],
            "concept_scope": self.reference + "#fields", "concept_id": field["id"],
            "codelist_scope": self.reference + "#" + field["id"] if "classification" in field else "",
        } for field in data["opendata_structures"][0]["dimensions"]]
        data["opendata_terms"] = [{
            "provider": "sample", "language": "en", "scope": self.reference + "#fields",
            "code": field["id"], "name": field["name"],
        } for field in data["opendata_structures"][0]["dimensions"]] + [{
            "provider": "sample", "language": "en", "scope": self.reference + "#TYPE", "code": code, "name": name,
        } for code, name in ((" ", "Native blank"), ("A", "Area A"))]
        data["opendata_documents"][0]["dataset_id"] = self.dataset
        return data

    def inspect(self, data):
        self.policy["document_contract_sha256"] = digest(self.contract)
        document, catalog = data["opendata_documents"][0], data["opendata_catalog"][0]
        inputs = Inputs(data, self.contract, digest)
        authority = {"title": catalog["title"], "metadata": {field: catalog.get(field) for field in (
            "names", "descriptions", "category_paths", "keywords", "caveat", "filters",
            "sources", "period_start", "period_end", "freshness",
        )}}
        document["projection"].update(contract_sha256=digest(self.contract),
                                      source_sha256=digest(inputs.envelope(inputs.prepare(catalog), "en", authority)))
        write_archive(self.archive, data, contract=self.contract)
        return inspect_archive(self.archive, self.policy)

    def test_native_layer_terms_and_empty_domains_have_exact_projections(self):
        data = self.data()
        report = self.inspect(data)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["tables"]["opendata_terms"], 6)
        self.assertEqual(data["opendata_terms"][-2]["code"], " ")
        self.assertEqual(data["opendata_structures"][0]["dimensions"][1]["classification"]["values"], [{"ONLY_NULL": None}])

    def test_arbitrary_url_scope_unknown_field_and_other_layer_are_rejected(self):
        for scope in ("https://unrelated.example/fields", self.reference + "#absent",
                      self.other + "#TYPE", "codelist:TYPE"):
            with self.subTest(scope=scope):
                data = self.data()
                data["opendata_terms"][-1]["scope"] = scope
                with self.assertRaises(QualityError):
                    self.inspect(data)

    def test_source_reference_matches_both_provider_and_catalogue(self):
        for location in ("structure", "catalogue", "provider"):
            with self.subTest(location=location):
                data = self.data()
                if location == "structure":
                    data["opendata_structures"][0]["source_reference"] += "/other"
                elif location == "catalogue":
                    data["opendata_catalog"][0]["sources"][0]["url"] += "/other"
                else:
                    self.contract["rendering"]["providers"]["sample"]["base_url"] += "/other"
                with self.assertRaisesRegex(ValueError, "catalogue layer"):
                    self.inspect(data)

    def test_fields_codes_labels_and_language_match_native_structure(self):
        for table, key, value in (
            ("opendata_structure_dims", "concept_id", "unknown"),
            ("opendata_structure_dims", "codelist_scope", self.reference + "#fields"),
            ("opendata_terms", "code", "invented"),
            ("opendata_terms", "name", "invented label"),
            ("opendata_terms", "language", "it"),
        ):
            with self.subTest(table=table, key=key):
                data = self.data()
                data[table][-1][key] = value
                with self.assertRaisesRegex(ValueError, "differs from its layer structure"):
                    self.inspect(data)

    def test_missing_native_dimension_or_term_is_rejected(self):
        for table in ("opendata_structure_dims", "opendata_terms"):
            with self.subTest(table=table):
                data = self.data()
                data[table].pop()
                with self.assertRaisesRegex(QualityError, "native vocabulary .* are missing"):
                    self.inspect(data)

    def test_empty_native_scope_cannot_supply_invented_terms(self):
        for scope in ("ONLY_NULL", "UNENUMERATED"):
            with self.subTest(scope=scope):
                data = self.data()
                data["opendata_terms"].append({"provider": "sample", "language": "en",
                    "scope": self.reference + "#" + scope, "code": "None", "name": "None"})
                with self.assertRaisesRegex(ValueError, "differs from its layer structure"):
                    self.inspect(data)

    def test_native_count_and_duplicate_codes_remain_checked(self):
        for change in ("count", "duplicate", "null"):
            with self.subTest(change=change):
                data = self.data()
                domain = data["opendata_structures"][0]["dimensions"][0]["classification"]
                if change == "count":
                    domain["non_null_distinct_count"] += 1
                else:
                    domain["values"].append(copy.deepcopy(domain["values"][0 if change == "null" else -1]))
                with self.assertRaisesRegex(ValueError, "native classification"):
                    self.inspect(data)

    def test_native_strategy_requires_its_source_language_and_vocabulary(self):
        for update in ({"driver": "sdmx"}, {"base_url": "https://source.example/path?query"}, {"extra": {}}):
            with self.subTest(update=update):
                held = copy.deepcopy(self.contract["rendering"]["providers"]["sample"])
                self.contract["rendering"]["providers"]["sample"].update(update)
                with self.assertRaisesRegex(ValueError, f"requires its {self.driver} source"):
                    self.inspect(self.data())
                self.contract["rendering"]["providers"]["sample"] = held
        self.policy["providers"]["sample"]["vocabulary"] = False
        with self.assertRaisesRegex(ValueError, f"requires its {self.driver} source"):
            self.inspect(self.data())

    def test_scope_strategy_is_required_explicit_configuration(self):
        source = (ROOT / "publisher.example.toml").read_text()
        path = Path(self.temporary.name) / "publisher.toml"
        for invalid in (source.replace('vocabulary_scopes = "prefixed"', "", 1),
                        source.replace('vocabulary_scopes = "prefixed"', 'vocabulary_scopes = "any_url"', 1),
                        source.replace("schema = 6", "schema = 5")):
            with self.subTest(invalid=invalid[:20]):
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    load(path)


class WfsVocabulary(NativeVocabulary):
    """The same rules for a layer a WFS describes: its URL is the service's DescribeFeatureType request."""

    def setUp(self):
        super().setUp()
        self.policy["providers"]["sample"]["vocabulary_scopes"] = "wfs_structure"
        self.driver = "wfs"
        self.base = "https://source.example"
        self.dataset = "plans:Zoning Plan"
        describe = self.base + "/geoserver/plans/ows?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames="
        self.reference = describe + "plans:Zoning+Plan"
        self.other = describe + "plans:Other"
        self.contract["rendering"]["providers"]["sample"].update(
            driver="wfs", base_url=self.base, extra={"catalog_language": "en", "wfs_policy": {
                "service": {"path": "geoserver/plans/ows", "version": "2.0.0"}}},
        )

    def test_wfs_strategy_requires_a_canonical_service_path_and_version(self):
        for service in ({"path": "geoserver/../ows", "version": "2.0.0"}, {"path": "geoserver/ows"}, None):
            with self.subTest(service=service):
                self.contract["rendering"]["providers"]["sample"]["extra"]["wfs_policy"] = {"service": service}
                with self.assertRaisesRegex(ValueError, "WFS service path and version"):
                    self.inspect(self.data())
