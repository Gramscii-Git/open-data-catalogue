"""Write a verified discovery archive as Parquet tables for S3: one directory per table, partitioned as declared."""

import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .archive import TABLE_KEYS

# DuckDB's own type names, as its DESCRIBE reads them back from Parquet.
TYPES = frozenset({"VARCHAR", "BOOLEAN", "BIGINT", "DATE", "TIMESTAMP WITH TIME ZONE", "JSON", "VARCHAR[]", "BLOB"})
# The largest object DuckDB's JSON reader asks for in one read of a pipe, which macOS caps at INT_MAX; its buffers
# grow only as far as a row needs, and a refused row fails the export.
LARGEST_OBJECT = 2**31 - 1


def load_tables(path: Path) -> dict:
    """Every archive table's declared columns, with the DuckDB type each is written as, and its partition column."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {"schema", "tables"} or spec["schema"] != 1:
        raise ValueError("S3 table declaration must be schema 1 with tables")
    tables = spec["tables"]
    if not isinstance(tables, dict) or set(tables) != set(TABLE_KEYS):
        raise ValueError("S3 table declaration must declare exactly the archive tables")
    for name, table in tables.items():
        if not isinstance(table, dict) or set(table) != {"partition", "columns"}:
            raise ValueError(f"{name}: declaration must contain exactly partition and columns")
        columns = table["columns"]
        if not isinstance(columns, dict) or not columns or any(kind not in TYPES for kind in columns.values()):
            raise ValueError(f"{name}: every column needs one of {sorted(TYPES)}")
        if any(re.fullmatch(r"[a-z_][a-z0-9_]*", column) is None for column in columns):
            raise ValueError(f"{name}: column names must be lowercase identifiers")
        if set(TABLE_KEYS[name]) - set(columns):
            raise ValueError(f"{name}: declared columns lack the table key")
        partition = table["partition"]
        if partition is not None and (partition not in TABLE_KEYS[name] or columns[partition] != "VARCHAR"):
            raise ValueError(f"{name}: a partition must be a text column of the table key")
    return tables


def copy_statement(table: dict, target: Path) -> str:
    """DuckDB's COPY of newline-delimited rows on standard input into Parquet; BLOB columns arrive as base64."""
    if "'" in str(target):
        raise ValueError("S3 export path cannot contain a quote")
    columns = table["columns"]
    read = ", ".join(f"'{column}': '{'VARCHAR' if kind == 'BLOB' else kind}'" for column, kind in columns.items())
    select = ", ".join(f"from_base64({column}) AS {column}" if kind == "BLOB" else column
                       for column, kind in columns.items())
    source = (f"read_json('/dev/stdin', format='newline_delimited', maximum_object_size={LARGEST_OBJECT}, "
              f"columns={{{read}}})")
    if table["partition"] is None:
        return f"COPY (SELECT {select} FROM {source}) TO '{target / 'data_0.parquet'}' (FORMAT parquet, COMPRESSION zstd)"
    return (f"COPY (SELECT {select} FROM {source}) TO '{target}' "
            f"(FORMAT parquet, COMPRESSION zstd, PARTITION_BY ({table['partition']}))")


def write_table(lines, name: str, table: dict, duckdb: list[str], target: Path) -> tuple[int, str, int]:
    """Stream one archive member into DuckDB, refusing a row whose columns differ from the declaration; answer
    with its rows, SHA-256 and bytes."""
    columns = set(table["columns"])
    checksum, rows, size = hashlib.sha256(), 0, 0
    target.mkdir()
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([*duckdb, "-c", copy_statement(table, target)],
                                   stdin=subprocess.PIPE, stdout=errors, stderr=errors)
        try:
            for line in lines:
                row = json.loads(line)
                if not isinstance(row, dict) or set(row) != columns:
                    raise ValueError(f"{name}: row {rows + 1} does not hold exactly the declared columns")
                checksum.update(line)
                size += len(line)
                rows += 1
                process.stdin.write(line)
            process.stdin.close()
        except BrokenPipeError:
            pass
        except BaseException:
            process.kill()
            process.wait()
            raise
        if process.wait() != 0 or not process.stdin.closed:
            errors.seek(0)
            raise RuntimeError(f"{name}: DuckDB did not write the table: {errors.read().decode(errors='replace').strip()}")
    return rows, checksum.hexdigest(), size


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


def export(archive: Path, expected_sha256: str, tables: dict, duckdb: list[str], output: Path) -> dict:
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
                written[name] = write_table(source.extractfile(member), name, tables[name], duckdb, output / name)
        if manifest is None or set(written) != set(tables):
            raise ValueError("archive must hold every declared table and its manifest")
        counted = {}
        for name, (rows, digest, size) in written.items():
            if manifest["tables"][name] != rows or manifest["members"][f"{name}.jsonl"] != {"sha256": digest, "bytes": size}:
                raise ValueError(f"{name}: rows or bytes differ from the archive manifest")
            per_file, columns = read_back(duckdb, output / name, tables[name])
            if sum(per_file.values()) != rows or columns != tables[name]["columns"]:
                raise ValueError(f"{name}: Parquet read-back differs from the archive")
            counted.update({str(Path(path).resolve()): value for path, value in per_file.items()})
        files = {str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha256_file(path),
                                                 "rows": counted[str(path.resolve())]}
                 for path in sorted(output.rglob("*.parquet"))}
        result = {
            "schema": 1,
            "taken_at": manifest["taken_at"],
            "archive": {"sha256": expected_sha256, "bytes": archive.stat().st_size},
            "document_contract": manifest["document_contract"],
            "document_contract_sha256": manifest["document_contract_sha256"],
            "tables": {name: {"rows": written[name][0], **tables[name]} for name in tables},
            "files": files,
        }
        (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(output)
        raise
    return result
