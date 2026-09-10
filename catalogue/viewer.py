"""Project verified archive rows into explicitly typed Hub viewer tables."""

import hashlib
import json
import re
import tarfile
from pathlib import PurePosixPath


def load(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if set(config) != {"schema_version", "tables", "column_sets"} or config["schema_version"] != 2:
        raise ValueError("unsupported viewer configuration")
    column_sets = config["column_sets"]
    if not isinstance(column_sets, dict) or not column_sets:
        raise ValueError("viewer column sets must be explicit and nonempty")
    tables = config["tables"]
    if not isinstance(tables, list) or not tables:
        raise ValueError("viewer tables must be explicit and nonempty")
    names, paths, used_columns = set(), set(), set()
    for table in tables:
        if set(table) != {"name", "archive", "member", "path", "split", "default", "columns"}:
            raise ValueError("viewer table fields are incomplete or unknown")
        for key in ("name", "split"):
            if not isinstance(table[key], str) or not re.fullmatch(r"[a-z][a-z0-9_]*", table[key]):
                raise ValueError("viewer identifiers must be canonical")
        if not isinstance(table["archive"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", table["archive"]) or type(table["default"]) is not bool:
            raise ValueError("viewer archive or default declaration is invalid")
        for key in ("member", "path"):
            value = table[key]
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or str(path) != value or path.suffix != ".jsonl":
                raise ValueError("viewer paths must be canonical relative JSONL paths")
        if table["name"] in names or table["path"] in paths:
            raise ValueError("viewer names and output paths must be unique")
        names.add(table["name"])
        paths.add(table["path"])
        column_set = table["columns"]
        if not isinstance(column_set, str) or column_set not in column_sets:
            raise ValueError("viewer table must reference a declared column set")
        used_columns.add(column_set)
        columns = column_sets[column_set]
        if not isinstance(columns, list) or not columns:
            raise ValueError("viewer columns must be explicit and nonempty")
        column_names = set()
        for column in columns:
            if set(column) != {"name", "source", "type", "nullable"}:
                raise ValueError("viewer column fields are incomplete or unknown")
            if not isinstance(column["name"], str) or not re.fullmatch(r"[a-z][a-z0-9_]*", column["name"]):
                raise ValueError("viewer column name is invalid")
            if column["name"] in column_names or column["type"] not in {"string", "bool", "json"}:
                raise ValueError("viewer columns must have unique names and supported types")
            column_names.add(column["name"])
            if type(column["nullable"]) is not bool or not isinstance(column["source"], list):
                raise ValueError("viewer column source and nullability must be explicit")
            if any(not isinstance(key, str) or not key for key in column["source"]):
                raise ValueError("viewer source paths must contain nonempty keys")
        table["columns"] = columns
    if used_columns != set(column_sets):
        raise ValueError("viewer column sets must be referenced by a table")
    if sum(table["default"] for table in tables) != 1:
        raise ValueError("viewer must declare exactly one default table")
    return tables


def project(row, columns):
    result = {}
    for column in columns:
        value = row
        for key in column["source"]:
            if value is None and column["nullable"]:
                break
            if not isinstance(value, dict) or key not in value:
                raise ValueError(f"viewer source field is missing: {column['source']}")
            value = value[key]
        if value is None:
            if not column["nullable"]:
                raise ValueError(f"viewer field cannot be null: {column['name']}")
        elif column["type"] == "json":
            value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        elif type(value) is not {"string": str, "bool": bool}[column["type"]]:
            raise ValueError(f"viewer field has the wrong type: {column['name']}")
        result[column["name"]] = value
    return result


def prepare(directory, tables, archives, reports):
    if {table["archive"] for table in tables} != set(archives) or set(archives) != set(reports):
        raise ValueError("viewer tables must cover exactly the declared archive set")
    metadata, files = [], []
    for table in tables:
        report = reports[table["archive"]]
        output = directory / table["path"]
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with tarfile.open(archives[table["archive"]], "r:gz") as archive, output.open("x", encoding="utf-8") as target:
            for line in archive.extractfile(table["member"]):
                row = project(json.loads(line), table["columns"])
                target.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                count += 1
        member = table["member"].removesuffix(".jsonl") if table["archive"] == "catalogue" else table["member"]
        if count != report["tables"][member]:
            raise ValueError("viewer row count differs from its validated archive")
        with output.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": table["path"], "rows": count, "sha256": digest,
                      "bytes": output.stat().st_size, "source_archive": table["archive"], "source_sha256": report["sha256"]})
        metadata.append({"config_name": table["name"], "default": table["default"],
                         "data_files": [{"split": table["split"], "path": table["path"]}],
                         "features": [{"name": column["name"], "dtype": "string" if column["type"] == "json" else column["type"]}
                                      for column in table["columns"]]})
    (directory / "viewer-manifest.json").write_text(json.dumps({"schema_version": 1, "files": files}, indent=2), encoding="utf-8")
    return "configs: " + json.dumps(metadata, ensure_ascii=False)
