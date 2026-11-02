"""The series inventory released beside the catalogue archive: per provider, the harvester's tables and blocks as
Parquet files, and the manifest that names each file's rows and SHA-256 and the tables left out with their reason.
Nothing is uploaded unless every file matches the manifest, the rows each Parquet footer declares match it, the
directory holds no other file, and every provider is one the catalogue archive holds."""

import hashlib
import json
import re
import shutil
from pathlib import Path

# Where the inventory sits in a release, and its manifest's name, as the harvester's series-export writes it.
DIRECTORY = "series"
MANIFEST = "series-manifest.json"
PARTS = ("tables", "blocks")
# A Parquet file starts and ends with this magic; the footer's length is the four bytes before the closing one.
MAGIC = b"PAR1"
# Thrift compact types, as the Parquet footer encodes FileMetaData with them.
BOOLEAN_TRUE, BOOLEAN_FALSE, BYTE, I16, I32, I64, DOUBLE, BINARY, LIST, SET, MAP, STRUCT = range(1, 13)
# FileMetaData's field holding the file's total rows.
NUM_ROWS = 3


class SeriesError(ValueError):
    """A series inventory that cannot be released as it is."""


def export(directory: Path, config: dict, harvester, providers) -> dict:
    """The harvester's inventory written into the release and checked whole: the export's own report must name the
    same providers, rows and left-out tables as the manifest it wrote."""
    target = directory / DIRECTORY
    reported = json.loads(harvester(config, "series-export", "--to", str(target), capture=True))
    checked = check(target, providers)
    if reported != checked["providers"]:
        raise SeriesError("series export report does not match its manifest")
    return checked


def stage(directory: Path, source: Path, providers) -> dict:
    """An inventory the harvester exported with the archive being published, copied into the release and checked."""
    target = directory / DIRECTORY
    shutil.copytree(source, target)
    return check(target, providers)


def files(directory: Path, providers) -> list[str]:
    """The release's inventory files to upload, each checked again against the manifest."""
    return check(directory / DIRECTORY, providers)["files"]


def check(target: Path, providers) -> dict:
    """Each provider's counts and the files to upload, once the manifest, the files and their footers agree."""
    manifest = json.loads((target / MANIFEST).read_bytes())
    if not isinstance(manifest, dict) or set(manifest) != {"providers"}:
        raise SeriesError("series manifest must hold exactly its providers")
    held = manifest["providers"]
    if not isinstance(held, dict) or not held:
        raise SeriesError("series manifest names no provider")
    unknown = sorted(set(held) - set(providers))
    if unknown:
        raise SeriesError(f"series manifest names providers the catalogue archive does not hold: {unknown}")
    counts, declared = {}, [MANIFEST]
    for provider, entry in sorted(held.items()):
        if not isinstance(entry, dict) or set(entry) != {*PARTS, "left_out"}:
            raise SeriesError(f"series manifest entry of {provider} must hold {sorted({*PARTS, 'left_out'})}")
        for part in PARTS:
            declared.append(_checked_file(target, provider, part, entry[part]))
        counts[provider] = {"tables": entry["tables"]["rows"], "blocks": entry["blocks"]["rows"],
                            "left_out": _left_out(provider, entry["left_out"])}
    present = sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file())
    if present != sorted(declared):
        raise SeriesError(f"series directory holds {present}, not the manifest's {sorted(declared)}")
    return {"providers": counts, "files": [f"{DIRECTORY}/{name}" for name in declared]}


def _checked_file(target: Path, provider: str, part: str, declared) -> str:
    if not isinstance(declared, dict) or set(declared) != {"file", "rows", "sha256"}:
        raise SeriesError(f"series {part} of {provider} must declare its file, rows and sha256")
    name, rows, sha256 = declared["file"], declared["rows"], declared["sha256"]
    parts = name.split("/") if isinstance(name, str) else []
    if len(parts) != 2 or parts[0] != provider or parts[1] in ("", ".", "..") or not parts[1].endswith(".parquet"):
        raise SeriesError(f"series {part} of {provider} must be a Parquet file in the provider's directory")
    if type(rows) is not int or rows < 0:
        raise SeriesError(f"{name} must declare a count of rows")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise SeriesError(f"{name} must declare a SHA-256")
    path = target / name
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != sha256:
        raise SeriesError(f"{name} is not the file the manifest names: sha256 {actual}, declared {sha256}")
    footer = parquet_rows(path)
    if footer != rows:
        raise SeriesError(f"{name} holds {footer} rows by its footer, the manifest declares {rows}")
    return name


def _left_out(provider: str, left_out) -> int:
    if not isinstance(left_out, list):
        raise SeriesError(f"series tables left out of {provider} must be a list")
    seen = set()
    for table in left_out:
        if (not isinstance(table, dict) or set(table) != {"dataset_id", "reason"}
                or not all(isinstance(table[key], str) and table[key] for key in ("dataset_id", "reason"))):
            raise SeriesError(f"each table left out of {provider} must name its dataset and its reason")
        if table["dataset_id"] in seen:
            raise SeriesError(f"{provider} leaves {table['dataset_id']} out twice")
        seen.add(table["dataset_id"])
    return len(left_out)


def parquet_rows(path: Path) -> int:
    """The rows a Parquet file declares: FileMetaData's num_rows, read from its footer."""
    size = path.stat().st_size
    with path.open("rb") as stream:
        if size < 12 or stream.read(4) != MAGIC:
            raise SeriesError(f"{path.name} does not start as a Parquet file")
        stream.seek(size - 8)
        tail = stream.read(8)
        if tail[4:] != MAGIC:
            raise SeriesError(f"{path.name} does not end as a Parquet file")
        length = int.from_bytes(tail[:4], "little")
        if not 0 < length <= size - 12:
            raise SeriesError(f"{path.name} declares a footer of {length} bytes in a file of {size}")
        stream.seek(size - 8 - length)
        footer = stream.read(length)
    return _Compact(footer).num_rows()


class _Compact:
    """Thrift's compact protocol, read far enough to walk any struct and take FileMetaData's row count."""

    def __init__(self, data: bytes):
        self.data, self.at = data, 0

    def num_rows(self) -> int:
        for field, kind in self.fields():
            if field == NUM_ROWS:
                if kind != I64:
                    raise SeriesError("Parquet footer's num_rows is not an i64")
                return self.zigzag()
            self.skip(kind)
        raise SeriesError("Parquet footer holds no num_rows")

    def fields(self):
        last = 0
        while (header := self.byte()) != 0:
            delta, kind = header >> 4, header & 0x0F
            last = last + delta if delta else self.zigzag()
            yield last, kind

    def skip(self, kind: int, *, element: bool = False) -> None:
        if kind in (BOOLEAN_TRUE, BOOLEAN_FALSE):
            # A field carries its boolean in its header; a collection's element takes one byte.
            if element:
                self.byte()
        elif kind == BYTE:
            self.byte()
        elif kind in (I16, I32, I64):
            self.varint()
        elif kind == DOUBLE:
            self.advance(8)
        elif kind == BINARY:
            self.advance(self.varint())
        elif kind in (LIST, SET):
            header = self.byte()
            size = header >> 4
            if size == 15:
                size = self.varint()
            for _ in range(size):
                self.skip(header & 0x0F, element=True)
        elif kind == MAP:
            size = self.varint()
            if size:
                types = self.byte()
                for _ in range(size):
                    self.skip(types >> 4, element=True)
                    self.skip(types & 0x0F, element=True)
        elif kind == STRUCT:
            for _, field_kind in self.fields():
                self.skip(field_kind)
        else:
            raise SeriesError(f"Parquet footer holds an unknown Thrift compact type {kind}")

    def byte(self) -> int:
        if self.at >= len(self.data):
            raise SeriesError("Parquet footer ends inside a value")
        self.at += 1
        return self.data[self.at - 1]

    def advance(self, count: int) -> None:
        if count < 0 or self.at + count > len(self.data):
            raise SeriesError("Parquet footer ends inside a value")
        self.at += count

    def varint(self) -> int:
        shift = value = 0
        while True:
            byte = self.byte()
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7

    def zigzag(self) -> int:
        value = self.varint()
        return (value >> 1) ^ -(value & 1)
