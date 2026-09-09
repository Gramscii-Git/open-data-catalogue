"""Publish licensed response projections pinned to an independently validated availability index."""

import hashlib
import json
import shutil
import tarfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from .availability import _sha, inspect_availability, policy_from
from .config import fields, text
from .publish import upload_files


def inspect(directory, availability, policy):
    index = inspect_availability(availability, policy)
    path = directory / "manifest.json"
    if path.is_symlink() or path.stat().st_size > policy["max_line_bytes"]:
        raise ValueError("source snapshot manifest exceeds its metadata byte budget")
    body = path.read_bytes()
    manifest = json.loads(body)
    fields(manifest, {"schema_version", "availability_sha256", "providers", "projections", "responses"}, "snapshot manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("source snapshot schema must be 1")
    if manifest["availability_sha256"] != index["sha256"]:
        raise ValueError("source snapshots identify a different availability archive")
    providers = manifest["providers"]
    if not isinstance(providers, dict) or not providers:
        raise ValueError("source snapshots require explicit provider definitions")
    definitions, expected = {}, {}
    with tarfile.open(availability, "r:gz") as archive:
        for line in archive.extractfile("datasets.jsonl"):
            dataset = json.loads(line)
            if dataset["provider"] in providers:
                definitions.setdefault(dataset["provider"], {})[dataset["dataset_id"]] = dataset["definition_sha256"]
        for line in archive.extractfile("partitions.jsonl"):
            partition = json.loads(line)
            if partition["provider"] not in providers:
                continue
            receipt = partition["receipts"][-1]
            declaration = {"provider": partition["provider"], "source": receipt}
            previous = expected.setdefault(receipt["sha256"], declaration)
            if previous != declaration:
                raise ValueError("one archived source digest has inconsistent indexed receipts")
    if definitions != providers:
        raise ValueError("source snapshot definitions differ from the complete selected provider scope")
    permitted = projection_fields(manifest["projections"], providers)
    responses = manifest["responses"]
    if not isinstance(responses, dict) or set(responses) != set(expected):
        raise ValueError("source snapshots omit or add indexed native responses")
    assets = {}
    for key, asset in responses.items():
        _sha(key)
        fields(asset, {"sha256", "bytes"}, "snapshot asset")
        _sha(asset["sha256"])
        if type(asset["bytes"]) is not int or not 0 < asset["bytes"] <= policy["max_line_bytes"]:
            raise ValueError("source snapshot asset exceeds its response byte budget")
        if assets.setdefault(asset["sha256"], asset["bytes"]) != asset["bytes"]:
            raise ValueError("source snapshot asset has inconsistent sizes")
    filenames = {f"responses/{digest}.json" for digest in assets}
    if {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()} != filenames | {"manifest.json"}:
        raise ValueError("source snapshot directory has missing or undeclared files")
    seen, size = set(), len(body)
    for digest, count in assets.items():
        file = directory / f"responses/{digest}.json"
        if file.is_symlink() or file.stat().st_size != count:
            raise ValueError("source snapshot asset has an invalid type or byte count")
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("source snapshot asset differs from its content digest")
        size += count
        if size > policy["max_unpacked_bytes"]:
            raise ValueError("source snapshots exceed the total byte budget")
        bundle = json.loads(raw)
        fields(bundle, {"schema_version", "responses"}, "snapshot bundle")
        if type(bundle["schema_version"]) is not int or bundle["schema_version"] != 1 or not isinstance(bundle["responses"], dict) or not bundle["responses"]:
            raise ValueError("source snapshot bundle requires its declared response map")
        for key, response in bundle["responses"].items():
            fields(response, {"schema_version", "provider", "source", "payload"}, "snapshot response")
            if key in seen or key not in expected or responses[key] != {"sha256": digest, "bytes": count}:
                raise ValueError("source snapshot bundle has an unbound or repeated response")
            if (type(response["schema_version"]) is not int or response["schema_version"] != 1
                    or {name: response[name] for name in ("provider", "source")} != expected[key]
                    or not isinstance(response["payload"], dict) or not response["payload"]):
                raise ValueError("archived response disagrees with its indexed native receipt")
            if set(response["payload"]) != permitted[response["provider"]]:
                raise ValueError("archived response contains missing or unlicensed projection fields")
            seen.add(key)
    if seen != set(expected):
        raise ValueError("source snapshot bundles do not cover every indexed native response")
    return {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "availability_sha256": index["sha256"],
            "providers": providers, "responses": len(seen), "files": ["manifest.json", *sorted(filenames)]}


def projection_fields(projections, providers):
    if not isinstance(projections, dict) or projections.keys() != providers.keys():
        raise ValueError("source snapshots require projection rights for every provider")
    result = {}
    for name, projection in projections.items():
        fields(projection, {"identity_fields", "datasets"}, "source projection")
        datasets, identity = projection["datasets"], projection["identity_fields"]
        if (not isinstance(datasets, dict) or datasets.keys() != providers[name].keys()
                or not isinstance(identity, list) or len(set(identity)) != len(identity)):
            raise ValueError("source snapshot projection identities or datasets are incomplete")
        result[name] = {text(value, "snapshot identity field") for value in identity}
        for rights in datasets.values():
            fields(rights, {"licence", "attribution", "source_url", "fields"}, "source rights")
            for field in ("licence", "attribution", "source_url"):
                text(rights[field], field)
            address = urlsplit(rights["source_url"])
            if address.scheme != "https" or not address.hostname or address.username or address.password:
                raise ValueError("source snapshot attribution requires an HTTPS source URL")
            selected = rights["fields"]
            if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
                raise ValueError("source snapshot rights require distinct projection fields")
            result[name].update(text(value, "licensed snapshot field") for value in selected)
    return result


def publish(source, availability, directory, destination, config, policy_path):
    prefix = PurePosixPath(destination)
    if prefix.is_absolute() or not prefix.parts or any(part in {".", ".."} for part in prefix.parts) or str(prefix) != destination:
        raise ValueError("snapshot destination must be a canonical relative repository directory")
    report = inspect(source, availability, policy_from(policy_path))
    target = directory / destination
    target.mkdir(parents=True, exist_ok=False)
    for filename in report["files"]:
        path = target / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / filename, path)
    files = [str(prefix / name) for name in report["files"]]
    return upload_files(directory, config, files, str(prefix / "manifest.json"), report)
