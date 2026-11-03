"""The series inventory released beside the catalogue archive: rows read from each Parquet footer, the manifest
checked whole against the files and the export's report, and the files a release uploads. The fixture was written by
the harvester's own release writer; the ECB blocks file holds three row groups."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from catalogue import series
from catalogue.series import SeriesError, check, export, parquet_rows, stage

FIXTURE = Path(__file__).parent / "fixtures" / "series"
# The catalogue archive's providers with their datasets, as the quality report names them.
PROVIDERS = {"bis": 1, "ecb": 2, "istat": 3}
REPORTED = {"bis": {"tables": 1, "blocks": 1, "left_out": 0}, "ecb": {"tables": 2, "blocks": 5, "left_out": 1}}


class SeriesInventoryTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.release = self.root / "release"
        self.release.mkdir()

    def staged(self):
        target = self.release / series.DIRECTORY
        shutil.copytree(FIXTURE, target)
        return target

    def rewritten(self, change):
        target = self.staged()
        manifest = json.loads((target / series.MANIFEST).read_bytes())
        change(manifest["providers"])
        (target / series.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
        return target

    def test_rows_are_read_from_each_footer_whatever_its_row_groups(self):
        manifest = json.loads((FIXTURE / series.MANIFEST).read_bytes())
        for entry in manifest["providers"].values():
            for part in series.PARTS:
                self.assertEqual(parquet_rows(FIXTURE / entry[part]["file"]), entry[part]["rows"])
        self.assertEqual(parquet_rows(FIXTURE / "ecb" / "series-blocks.parquet"), 5)

    def test_a_file_that_is_not_parquet_is_refused(self):
        path = self.root / "unended.parquet"
        path.write_bytes(b"PAR1" + bytes(16))
        with self.assertRaisesRegex(SeriesError, "does not end as a Parquet file"):
            parquet_rows(path)
        path.write_bytes(b"CSV," + bytes(12) + b"PAR1")
        with self.assertRaisesRegex(SeriesError, "does not start as a Parquet file"):
            parquet_rows(path)

    def test_a_footer_longer_than_its_file_is_refused(self):
        path = self.root / "short.parquet"
        path.write_bytes(b"PAR1" + bytes(4) + (1000).to_bytes(4, "little") + b"PAR1")
        with self.assertRaisesRegex(SeriesError, "declares a footer of 1000 bytes in a file of 16"):
            parquet_rows(path)

    def test_a_footer_that_ends_inside_a_value_is_refused(self):
        # Field 1 as an i32 whose varint announces a byte the footer does not hold.
        footer = bytes([0x15, 0x80])
        path = self.root / "cut.parquet"
        path.write_bytes(b"PAR1" + footer + len(footer).to_bytes(4, "little") + b"PAR1")
        with self.assertRaisesRegex(SeriesError, "ends inside a value"):
            parquet_rows(path)

    def test_a_released_inventory_gives_its_counts_and_the_files_to_upload(self):
        checked = check(self.staged(), PROVIDERS)
        self.assertEqual(checked["providers"], REPORTED)
        files = ["series/series-manifest.json", "series/bis/series-tables.parquet", "series/bis/series-blocks.parquet",
                 "series/ecb/series-tables.parquet", "series/ecb/series-blocks.parquet"]
        self.assertEqual(checked["files"], files)
        self.assertEqual(series.files(self.release, PROVIDERS), files)

    def test_a_changed_file_is_refused(self):
        path = self.staged() / "ecb" / "series-blocks.parquet"
        changed = bytearray(path.read_bytes())
        changed[10] ^= 0xFF
        path.write_bytes(bytes(changed))
        with self.assertRaisesRegex(SeriesError, "ecb/series-blocks.parquet is not the file the manifest names"):
            check(path.parent.parent, PROVIDERS)

    def test_rows_the_footer_does_not_hold_are_refused(self):
        def more(providers):
            providers["ecb"]["blocks"]["rows"] = 6
        with self.assertRaisesRegex(SeriesError, "holds 5 rows by its footer, the manifest declares 6"):
            check(self.rewritten(more), PROVIDERS)

    def test_a_file_the_manifest_does_not_name_is_refused(self):
        target = self.staged()
        (target / "ecb" / "notes.txt").write_text("unreleased", encoding="utf-8")
        with self.assertRaisesRegex(SeriesError, "not the manifest's"):
            check(target, PROVIDERS)

    def test_a_provider_the_catalogue_archive_lacks_is_refused(self):
        with self.assertRaisesRegex(SeriesError, r"the catalogue archive does not hold: \['ecb'\]"):
            check(self.staged(), {"bis": 1})

    def test_a_file_outside_its_provider_directory_is_refused(self):
        def moved(providers):
            providers["ecb"]["tables"]["file"] = "bis/series-tables.parquet"
        with self.assertRaisesRegex(SeriesError, "a Parquet file in the provider's directory"):
            check(self.rewritten(moved), PROVIDERS)

    def test_a_table_left_out_names_its_reason(self):
        def unexplained(providers):
            providers["ecb"]["left_out"] = [{"dataset_id": "YC", "reason": ""}]
        with self.assertRaisesRegex(SeriesError, "must name its dataset and its reason"):
            check(self.rewritten(unexplained), PROVIDERS)

    def test_the_export_report_must_match_the_manifest_it_wrote(self):
        reported, calls = REPORTED, []

        def harvester(config, *arguments, capture=False):
            calls.append(arguments)
            shutil.copytree(FIXTURE, Path(arguments[arguments.index("--to") + 1]))
            return json.dumps(reported)

        self.assertEqual(export(self.release, {}, harvester, PROVIDERS)["providers"], REPORTED)
        self.assertEqual(calls, [("series-export", "--to", str(self.release / series.DIRECTORY))])
        other = self.root / "other"
        other.mkdir()
        reported = {**REPORTED, "ecb": {"tables": 2, "blocks": 4, "left_out": 1}}
        with self.assertRaisesRegex(SeriesError, "series export report does not match its manifest"):
            export(other, {}, harvester, PROVIDERS)

    def test_an_archive_published_alone_stages_the_inventory_exported_with_it(self):
        checked = stage(self.release, FIXTURE, PROVIDERS)
        self.assertEqual(checked["providers"], REPORTED)
        self.assertTrue((self.release / series.DIRECTORY / "ecb" / "series-blocks.parquet").is_file())


if __name__ == "__main__":
    unittest.main()
