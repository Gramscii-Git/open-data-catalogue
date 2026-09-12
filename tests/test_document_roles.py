"""Read independently produced document proofs without loading the core package."""

import copy
import gzip
import json
import unittest
from pathlib import Path

from catalogue.document_inputs import Inputs
from catalogue.documents import digest, inspect_contract, inspect_membership

FIXTURE = Path(__file__).parent / "fixtures/native-document-role-readback.json.gz"


class NativeDocumentRole(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(gzip.decompress(FIXTURE.read_bytes()))
        self.manifest = self.fixture["manifest"]
        self.contract = self.manifest["document_contract"]
        self.tables = self.fixture["tables"]
        self.row = self.tables["opendata_catalog"][0]
        self.member = self.row["inventory_memberships"]["registry"]
        self.source = self.member["record"]["fields"]["sources"][-1]
        self.policy = {
            "maximum_missing_documents": 0,
            "document_contract_sha256": self.manifest["document_contract_sha256"],
            "document_fields": self.contract["eligibility_fields"],
            "providers": {provider: {"languages": list(languages)} for provider, languages in self.contract["providers"].items()},
            "query_languages": list(self.contract["searches"]),
        }

    def inspect(self):
        contract = inspect_contract(self.manifest, self.policy)
        catalogue = {(row["provider"], row["dataset_id"]): row for row in self.tables["opendata_catalog"]}
        documents = {(row["provider"], row["dataset_id"], row["language"]): row for row in self.tables["opendata_documents"]}
        return inspect_membership(catalogue, documents, contract, self.manifest, self.tables)

    def update_native_source(self):
        self.row["sources"][-1] = copy.deepcopy(self.source)

    def test_real_core_snapshot_proofs_are_accepted_with_unused_legacy_structure(self):
        self.assertEqual(self.fixture["origin"]["core_revision"], "ee5fe5e2")
        self.assertEqual(self.manifest["schema_version"], 2)
        self.assertEqual(self.contract["schema_version"], 2)
        self.assertTrue(self.tables["opendata_structures"][0]["dimensions"])
        self.assertIsNone(self.tables["opendata_structures"][0]["source_reference"])
        metrics, issues = self.inspect()
        self.assertEqual(issues, [])
        self.assertEqual(metrics["invalid_document_projections"], 0)
        self.assertEqual(metrics["missing_documents"], 0)
        prepared = Inputs(self.tables, self.contract, digest).prepare(self.row)
        self.assertIsNone(prepared.structure)
        self.assertEqual(prepared.row["names"]["en"], "2014 tables")
        self.assertEqual(self.row["names"]["en"], "Historical title")
        self.assertEqual(prepared.role["membership"]["inventory"]["datasets"], 6)

    def test_missing_membership_cannot_bypass_structure_validation(self):
        self.row["inventory_memberships"] = {}
        with self.assertRaisesRegex(ValueError, "qualified lifecycle membership"):
            self.inspect()

    def test_absent_membership_and_structure_do_not_qualify_unserved_historical_names(self):
        self.row["inventory_memberships"] = {}
        self.row["sources"] = [source for source in self.row["sources"] if source["role"] != "structure-reference"]
        self.tables["opendata_structures"] = []
        with self.assertRaisesRegex(ValueError, "qualified lifecycle membership"):
            self.inspect()

    def test_queryable_flag_conflict_is_not_interpreted_as_descriptive_metadata(self):
        self.source["queryable"] = True
        self.update_native_source()
        with self.assertRaisesRegex(ValueError, "queryability contradicts"):
            self.inspect()

    def test_subset_count_cannot_impersonate_the_complete_inventory(self):
        self.member["inventory"]["datasets"] = 1
        self.member["record"]["inventory"]["datasets"] = 1
        with self.assertRaisesRegex(ValueError, "complete native inventory receipt"):
            self.inspect()

    def test_changed_native_annotation_invalidates_the_unchanged_document(self):
        self.source["registry"]["native"]["annotations"][2]["texts"][0]["text"] += "?revision=2"
        self.update_native_source()
        metrics, issues = self.inspect()
        self.assertEqual(metrics["invalid_document_projections"], 2)
        self.assertTrue(issues)

    def test_absent_native_language_is_not_filled_from_historical_catalogue_names(self):
        del self.source["registry"]["native"]["names"]["en"]
        del self.member["record"]["fields"]["names"]["en"]
        self.update_native_source()
        self.assertTrue(self.row["names"]["en"])
        metrics, issues = self.inspect()
        self.assertGreaterEqual(metrics["invalid_document_projections"], 1)
        self.assertTrue(issues)

    def test_role_configuration_is_required_and_never_supplied_as_a_default(self):
        del self.contract["source_roles"]["istat"]
        with self.assertRaisesRegex(ValueError, "source roles"):
            self.inspect()

    def test_previous_document_contract_version_is_explicitly_refused(self):
        self.contract["schema_version"] = 1
        with self.assertRaisesRegex(ValueError, "contract schema_version must be 2"):
            self.inspect()

    def test_nonqueryable_record_cannot_be_promoted_into_observation_eligibility(self):
        self.row["served"] = True
        with self.assertRaisesRegex(ValueError, "served contradicts"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
