"""Write a verified discovery archive as Parquet tables for S3: one directory per table, partitioned as declared."""

import base64
import binascii
import gzip
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .archive import PASSAGE_KEY, PASSAGES, TABLE_KEYS

# Every table the export writes, with its key: the archive's tables and its search passages.
KEYS = {**TABLE_KEYS, PASSAGES: PASSAGE_KEY}
# DuckDB's own type names, as its DESCRIBE reads them back from Parquet. A BLOB arrives as base64; a FLOAT[] arrives as
# base64 of little-endian float32 and is staged as its values.
TYPES = frozenset({"VARCHAR", "BOOLEAN", "BIGINT", "DATE", "TIMESTAMP WITH TIME ZONE", "JSON", "VARCHAR[]", "BLOB",
                   "FLOAT[]"})
# The longest row DuckDB's JSON reader may be told of, which macOS caps at INT_MAX for one read. Every reader thread
# holds two buffers of the declared length, so the declaration is the archive's longest row, not this cap.
LONGEST_READ = 2**31 - 1
# DuckDB reads each file's rows from a staged file, never from a pipe: rows read from a pipe stay in memory until
# the COPY ends, and one provider's structures reach 20 GB of rows of several MB. One thread reads them, and Parquet
# row groups close at this size.
ROW_GROUP_BYTES = "64MB"
# A partition value names a directory: lowercase letters, digits, hyphens and underscores.
PARTITION_VALUE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def load_tables(path: Path) -> dict:
    """Every archive table's declared columns, with the DuckDB type each is written as, and its partition column."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {"schema", "tables"} or spec["schema"] != 1:
        raise ValueError("S3 table declaration must be schema 1 with tables")
    tables = spec["tables"]
    if not isinstance(tables, dict) or set(tables) != set(KEYS):
        raise ValueError("S3 table declaration must declare exactly the archive tables")
    for name, table in tables.items():
        if not isinstance(table, dict) or set(table) != {"partition", "columns"}:
            raise ValueError(f"{name}: declaration must contain exactly partition and columns")
        columns = table["columns"]
        if not isinstance(columns, dict) or not columns or any(kind not in TYPES for kind in columns.values()):
            raise ValueError(f"{name}: every column needs one of {sorted(TYPES)}")
        if any(re.fullmatch(r"[a-z_][a-z0-9_]*", column) is None for column in columns):
            raise ValueError(f"{name}: column names must be lowercase identifiers")
        if set(KEYS[name]) - set(columns):
            raise ValueError(f"{name}: declared columns lack the table key")
        partition = table["partition"]
        if partition is not None and (partition not in KEYS[name] or columns[partition] != "VARCHAR"):
            raise ValueError(f"{name}: a partition must be a text column of the table key")
    return tables


def copy_statement(table: dict, source: Path, target: Path, *, memory_limit: str, longest_row: int) -> str:
    """DuckDB's COPY of the newline-delimited rows staged in `source` into the Parquet file `target`, without the
    partition column its directory names; BLOB columns arrive as base64. DuckDB reads rows of at most `longest_row`
    bytes with one thread, holds at most `memory_limit` and spills the rest to disk."""
    if "'" in str(source) or "'" in str(target):
        raise ValueError("S3 export path cannot contain a quote")
    if not re.fullmatch(r"[1-9][0-9]*(MB|GB)", memory_limit):
        raise ValueError(f"DuckDB memory limit {memory_limit!r} is not a size in MB or GB")
    if not 0 < longest_row <= LONGEST_READ:
        raise ValueError(f"longest row {longest_row} is not between 1 and {LONGEST_READ} bytes")
    columns = table["columns"]
    read = ", ".join(f"'{column}': '{'VARCHAR' if kind == 'BLOB' else kind}'" for column, kind in columns.items())
    select = ", ".join(f"from_base64({column}) AS {column}" if kind == "BLOB" else column
                       for column, kind in columns.items() if column != table["partition"])
    return (f"SET memory_limit='{memory_limit}'; SET threads=1; SET preserve_insertion_order=false; "
            f"COPY (SELECT {select} FROM read_json('{source}', format='newline_delimited', "
            f"maximum_object_size={longest_row}, columns={{{read}}})) "
            f"TO '{target}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE_BYTES '{ROW_GROUP_BYTES}')")


def write_table(lines, name: str, table: dict, duckdb: list[str], target: Path, *,
                memory_limit: str, longest_row: int) -> tuple[int, str, int]:
    """Stream one archive member into Parquet through DuckDB: one file, or one file for each partition value of a
    partitioned table, whose rows the archive carries grouped by that value. A row longer than `longest_row`, whose
    columns differ from the declaration, or whose partition value a directory cannot hold or that arrives again after
    another's, is refused. Answer with its rows, SHA-256 and bytes."""
    columns, partition = set(table["columns"]), table["partition"]
    vectors = [column for column, kind in table["columns"].items() if kind == "FLOAT[]"]
    checksum, rows, size = hashlib.sha256(), 0, 0
    target.mkdir()
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{name}-") as staging:
        staged = Path(staging) / "rows.jsonl.gz"
        written, value, sink = set(), None, None

        def copy() -> None:
            sink.close()
            directory = target / f"{partition}={value}" if partition is not None else target
            directory.mkdir(exist_ok=partition is None)
            statement = copy_statement(table, staged, directory / "data_0.parquet", memory_limit=memory_limit,
                                       longest_row=longest_row)
            result = subprocess.run([*duckdb, "-c", statement], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"{name}: DuckDB did not write the table: {(result.stderr or result.stdout).strip()}")
            written.add(value)

        for line in lines:
            if len(line) > longest_row:
                raise ValueError(f"{name}: row {rows + 1} holds {len(line)} bytes, past the longest row "
                                 f"declared ({longest_row})")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != columns:
                raise ValueError(f"{name}: row {rows + 1} does not hold exactly the declared columns")
            held = row[partition] if partition is not None else None
            if partition is not None and not (isinstance(held, str) and PARTITION_VALUE.fullmatch(held)):
                raise ValueError(f"{name}: row {rows + 1} names no {partition} a path can hold: {held!r}")
            if sink is None or held != value:
                if sink is not None:
                    copy()
                if held in written:
                    raise ValueError(f"{name}: rows of {partition} {held!r} arrive after another {partition}'s")
                value, sink = held, gzip.open(staged, "wb", compresslevel=1)
            checksum.update(line)
            size += len(line)
            rows += 1
            if vectors:
                # The archive's bytes are checked as they are; DuckDB reads each vector as its float32 values.
                for column in vectors:
                    row[column] = floats(row[column], f"{name}: row {rows} holds no float32 vector in {column}")
                staged_line = json.dumps(row, ensure_ascii=False, allow_nan=False).encode() + b"\n"
            else:
                staged_line = line if line.endswith(b"\n") else line + b"\n"
            sink.write(staged_line)
        if sink is None and partition is None:
            sink = gzip.open(staged, "wb", compresslevel=1)
        if sink is not None:
            copy()
    return rows, checksum.hexdigest(), size


def floats(value, refusal: str) -> list[float]:
    """The values of a vector carried as base64 of little-endian float32; refused with `refusal` for anything else."""
    try:
        raw = base64.b64decode(value, validate=True)
    except (TypeError, binascii.Error, ValueError):
        raw = b""
    if not raw or len(raw) % 4:
        raise ValueError(refusal)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def read_back(duckdb: list[str], target: Path, table: dict) -> tuple[dict[str, int], dict]:
    """The rows of each written file of a table and the column types DuckDB reads from it."""
    pattern = target / ("*/*.parquet" if table["partition"] else "data_0.parquet")
    partitioned = "true" if table["partition"] else "false"
    source = f"read_parquet('{pattern}', hive_partitioning={partitioned}, filename=true)"
    query = (f"SELECT filename, count(*) AS rows FROM {source} GROUP BY filename; "
             f"DESCRIBE SELECT * EXCLUDE (filename) FROM {source}")
    result = subprocess.run([*duckdb, "-json", "-c", query], check=True, capture_output=True, text=True)
    decoder = json.JSONDecoder()
    counted, end = decoder.raw_decode(result.stdout.strip())
    described, _ = decoder.raw_decode(result.stdout[end:].strip())
    return ({row["filename"]: row["rows"] for row in counted},
            {column["column_name"]: column["column_type"] for column in described})


def sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1 << 20):
            checksum.update(chunk)
    return checksum.hexdigest()


def export(archive: Path, expected_sha256: str, tables: dict, duckdb: list[str], output: Path, *,
           memory_limit: str, longest_row: int) -> dict:
    """Write every table of the archive whose bytes match the verified SHA-256 under `output`, check each against
    the archive manifest and its own read-back, and write `output/manifest.json` naming every file."""
    if output.exists():
        raise ValueError("S3 export directory must not exist")
    if sha256_file(archive) != expected_sha256:
        raise ValueError("archive does not match the verified SHA-256")
    output.mkdir(parents=True)
    try:
        written, manifest = {}, None
        with tarfile.open(archive, "r|gz") as source:
            for member in source:
                if member.name == "manifest.json" and member.isfile():
                    manifest = json.load(source.extractfile(member))
                    continue
                name = member.name.removesuffix(".jsonl")
                if not member.isfile() or member.name != f"{name}.jsonl" or name not in tables or name in written:
                    raise ValueError(f"archive member {member.name!r} is not a declared table")
                written[name] = write_table(source.extractfile(member), name, tables[name], duckdb, output / name,
                                            memory_limit=memory_limit, longest_row=longest_row)
        if manifest is None or set(written) != set(tables):
            raise ValueError("archive must hold every declared table and its manifest")
        counted = {}
        for name, (rows, digest, size) in written.items():
            declared = manifest["passages"]["rows"] if name == PASSAGES else manifest["tables"][name]
            if declared != rows or manifest["members"][f"{name}.jsonl"] != {"sha256": digest, "bytes": size}:
                raise ValueError(f"{name}: rows or bytes differ from the archive manifest")
            if tables[name]["partition"] is not None and rows == 0:
                continue  # a partitioned table without rows writes no file to read back
            per_file, columns = read_back(duckdb, output / name, tables[name])
            if sum(per_file.values()) != rows or columns != tables[name]["columns"]:
                raise ValueError(f"{name}: Parquet read-back differs from the archive")
            counted.update({str(Path(path).resolve()): value for path, value in per_file.items()})
        files = {str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha256_file(path),
                                                 "rows": counted[str(path.resolve())]}
                 for path in sorted(output.rglob("*.parquet"))}
        result = {
            "schema": 2,
            "taken_at": manifest["taken_at"],
            "archive": {"sha256": expected_sha256, "bytes": archive.stat().st_size},
            "document_contract": manifest["document_contract"],
            "document_contract_sha256": manifest["document_contract_sha256"],
            "tables": {name: {"rows": written[name][0], **tables[name]} for name in tables},
            # The embedder the passages' vectors come from: a reader lays them only when it embeds with the same.
            "passages": {"embedder": manifest["passages"]["embedder"]},
            "files": files,
        }
        (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(output)
        raise
    return result
