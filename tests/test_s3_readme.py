"""The S3 README is written from the release's manifest. The fixture is R7's manifest as the schema 2 export writes it
(R7's archive held no passages, and the embedder is the one SDG's card pins): it gives back the words and numbers of the
README published with R7, laid out by one rule, with what schema 2 adds."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from catalogue import s3_readme

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/s3-r7-manifest.json").read_text(encoding="utf-8"))
TEMPLATE = (ROOT / "s3-readme.txt").read_text(encoding="utf-8")
DECLARED = s3_readme.load(ROOT / "s3-readme.json")
PUBLISHED_R7 = (ROOT / "tests/fixtures/s3-r7-README.txt").read_text(encoding="utf-8")
# What schema 2 adds to R7's README: the passages' vectors, the manifest's embedder and the passages' table.
SCHEMA_2 = (
    ("geometries, rasters or granules, and no search vectors: values stay with the original provider, which each entry "
     "names and links.",
     "geometries, rasters or granules: values stay with the original provider, which each entry names and links. Its "
     "searchable descriptions are cut into passages, each with a vector of 768 float32 values made by the embedder "
     "manifest.json pins."),
    ("and every column with its type) and files",
     "and every column with its type), passages (the embedder the vectors come from: the SHA-256 of each of its files "
     "and the dimensions of its space) and files"),
    ("check the files you read against it.",
     "check the files you read against it; lay the passages' vectors only beside vectors of the same embedder."),
    ("searchable description, per language opendata_native_objects",
     "searchable description, per language opendata_passages 0 one per passage of a searchable description: its "
     "place, its text and its vector opendata_native_objects"),
)


def r7_with_schema_2() -> list[str]:
    words = " ".join(PUBLISHED_R7.split())
    for published, written in SCHEMA_2:
        assert words.count(published) == 1, published
        words = words.replace(published, written)
    return words.split()


def section(text: str, heading: str) -> list[str]:
    """The lines under `heading`'s underline up to the first blank line."""
    lines = text.splitlines()
    start = lines.index(heading) + 2
    return lines[start:lines.index("", start)]


class S3ReadmeTest(unittest.TestCase):
    def test_r7_manifest_gives_r7_counts(self):
        text = s3_readme.written(TEMPLATE, MANIFEST, DECLARED)
        self.assertIn("A catalogue of 78,150 public datasets from 34 European", text)
        self.assertIn("snapshot taken 2026-11-11T19:00:06Z", text)
        self.assertIn(f"SHA-256 {MANIFEST['archive']['sha256']}", text)
        for name, table in MANIFEST["tables"].items():
            self.assertRegex(text, rf"(?m)^{name}\s+{table['rows']:,}\s")
        self.assertNotIn("$", text)
        self.assertEqual(text.split(), r7_with_schema_2())
        generated = section(text, "Providers (partition ids)") + section(text, "Tables (rows in this release)")
        self.assertEqual(len(generated), 28)
        self.assertTrue(all(len(line) <= s3_readme.WIDTH for line in generated))

    def test_rows_and_dimensions_follow_the_manifest(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["tables"]["opendata_catalog"]["rows"] = 80001
        manifest["tables"]["opendata_passages"]["rows"] = 1234567
        manifest["passages"]["embedder"]["dimensions"] = 1024
        text = s3_readme.written(TEMPLATE, manifest, DECLARED)
        self.assertIn("A catalogue of 80,001 public datasets", text)
        self.assertRegex(text, r"(?m)^opendata_passages\s+1,234,567\s")
        self.assertIn("a\nvector of 1024 float32 values", text)

    def test_a_schema_1_manifest_refuses(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["schema"] = 1
        with self.assertRaisesRegex(ValueError, "schema 2"):
            s3_readme.written(TEMPLATE, manifest, DECLARED)

    def test_an_ungrouped_provider_refuses(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["files"]["opendata_catalog/provider=palermo/data_0.parquet"] = {"rows": 1}
        with self.assertRaisesRegex(ValueError, "not grouped \\['palermo'\\]"):
            s3_readme.written(TEMPLATE, manifest, DECLARED)

    def test_a_grouped_provider_the_release_lacks_refuses(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["files"] = {path: file for path, file in manifest["files"].items() if "provider=roma/" not in path}
        with self.assertRaisesRegex(ValueError, "not in the release \\['roma'\\]"):
            s3_readme.written(TEMPLATE, manifest, DECLARED)

    def test_an_undescribed_table_refuses(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["tables"]["opendata_new"] = {"rows": 3}
        with self.assertRaisesRegex(ValueError, "other tables"):
            s3_readme.written(TEMPLATE, manifest, DECLARED)

    def test_a_provider_in_two_groups_refuses(self):
        declared = json.loads((ROOT / "s3-readme.json").read_text(encoding="utf-8"))
        declared["groups"][1]["providers"].append("istat")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s3-readme.json"
            path.write_text(json.dumps(declared), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "one group"):
                s3_readme.load(path)


if __name__ == "__main__":
    unittest.main()
