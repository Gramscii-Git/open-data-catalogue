"""Project verified archive rows into explicitly typed Hub viewer tables."""

import hashlib
import json
import re
import tarfile
from pathlib import PurePosixPath
import urllib.request

from .publish import file_url


def _configuration(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if set(config) != {"schema_version", "tables", "column_sets", "published"} or config["schema_version"] != 3:
        raise ValueError("unsupported viewer configuration")
    if not isinstance(config["published"], list):
        raise ValueError("published viewer tables must be an explicit list")
    return config


def load(path):
    config = _configuration(path)
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


def _published_entry(value):
    expected = {
        "provider", "destination", "revision", "viewer_sha256", "viewer_bytes", "data_bytes"
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("published viewer entry fields are incomplete or unknown")
    provider = value["provider"]
    if not isinstance(provider, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", provider):
        raise ValueError("published viewer provider is invalid")
    destination = PurePosixPath(value["destination"])
    if str(destination) != value["destination"] or destination.parts != ("providers", provider):
        raise ValueError("published viewer destination must identify its provider directory")
    if not isinstance(value["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["revision"]):
        raise ValueError("published viewer revision must be an immutable full commit")
    if not isinstance(value["viewer_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["viewer_sha256"]):
        raise ValueError("published viewer receipt requires a SHA-256 digest")
    if type(value["viewer_bytes"]) is not int or value["viewer_bytes"] <= 0:
        raise ValueError("published viewer receipt requires a positive byte count")
    if type(value["data_bytes"]) is not int or value["data_bytes"] <= 0:
        raise ValueError("published viewer data requires a positive byte count")
    return value


def _download(url, sha256, size, timeout):
    digest = hashlib.sha256()
    content = bytearray()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"published viewer download returned HTTP {response.status}")
        while block := response.read(1024 * 1024):
            content.extend(block)
            digest.update(block)
            if len(content) > size:
                raise RuntimeError("published viewer download exceeds its declared byte count")
    if len(content) != size or digest.hexdigest() != sha256:
        raise RuntimeError("published viewer download does not match its size and SHA-256")
    return bytes(content)


def published(path, hub):
    config = _configuration(path)
    tables = load(path)
    catalogue = [table for table in tables if table["name"] == "catalogue"]
    if len(catalogue) != 1:
        raise ValueError("published provider viewers require exactly one catalogue table")
    columns = catalogue[0]["columns"]
    metadata, evidence = [], []
    names = {table["name"] for table in tables}
    paths = {table["path"] for table in tables}
    for raw in config["published"]:
        entry = _published_entry(raw)
        receipt_path = f"{entry['destination']}/viewer.json"
        receipt_bytes = _download(
            file_url(hub, entry["revision"], receipt_path),
            entry["viewer_sha256"],
            entry["viewer_bytes"],
            hub["timeout_seconds"],
        )
        receipt = json.loads(receipt_bytes)
        expected = {"schema_version", "config_name", "rows", "path", "sha256", "source_sha256"}
        if not isinstance(receipt, dict) or set(receipt) != expected or receipt["schema_version"] != 1:
            raise ValueError("published provider viewer receipt is invalid")
        if not isinstance(receipt["config_name"], str) or not re.fullmatch(r"[a-z][a-z0-9_]*", receipt["config_name"]):
            raise ValueError("published provider viewer config name is invalid")
        data_path = PurePosixPath(receipt["path"])
        if data_path.parts != ("catalogue.jsonl",) or type(receipt["rows"]) is not int or receipt["rows"] <= 0:
            raise ValueError("published provider viewer data declaration is invalid")
        for name in ("sha256", "source_sha256"):
            if not isinstance(receipt[name], str) or not re.fullmatch(r"[0-9a-f]{64}", receipt[name]):
                raise ValueError("published provider viewer data requires SHA-256 identities")
        target = str(PurePosixPath(entry["destination"]) / data_path)
        if receipt["config_name"] in names or target in paths:
            raise ValueError("published viewer names and paths must be unique")
        names.add(receipt["config_name"])
        paths.add(target)
        data = _download(
            file_url(hub, entry["revision"], target),
            receipt["sha256"],
            entry["data_bytes"],
            hub["timeout_seconds"],
        )
        if len(data.splitlines()) != receipt["rows"]:
            raise ValueError("published provider viewer row count differs from its receipt")
        metadata.append({
            "config_name": receipt["config_name"],
            "default": False,
            "data_files": [{"split": "data", "path": target}],
            "features": [
                {"name": column["name"], "dtype": "string" if column["type"] == "json" else column["type"]}
                for column in columns
            ],
        })
        evidence.append({**entry, **receipt, "path": target})
    return metadata, evidence


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


def prepare(directory, tables, archives, reports, external=((), ())):
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
    external_metadata, external_files = external
    metadata.extend(external_metadata)
    (directory / "viewer-manifest.json").write_text(json.dumps({
        "schema_version": 2,
        "files": files,
        "published_files": external_files,
    }, indent=2), encoding="utf-8")
    return "configs: " + json.dumps(metadata, ensure_ascii=False)


def update_card(readme, external_metadata):
    lines = readme.splitlines(keepends=True)
    indexes = [index for index, line in enumerate(lines) if line.startswith("configs: ")]
    if len(indexes) != 1:
        raise ValueError("Hub card must contain exactly one JSON configs declaration")
    index = indexes[0]
    configs = json.loads(lines[index].removeprefix("configs: "))
    external_names = {config["config_name"] for config in external_metadata}
    retained = [config for config in configs if config.get("config_name") not in external_names]
    paths = {item["data_files"][0]["path"] for item in retained}
    if any(item["data_files"][0]["path"] in paths for item in external_metadata):
        raise ValueError("published viewer path collides with an existing Hub config")
    lines[index] = "configs: " + json.dumps([*retained, *external_metadata], ensure_ascii=False) + "\n"
    return "".join(lines)
