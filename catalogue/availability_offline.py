"""Validate pinned offline SDMX provenance before staging an availability publication."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .archive import digest
from .availability import MEMBERS, _sha, _time, inspect_availability, policy_from
from .availability_build import verify_build
from .availability_scope import verify_inventory_scope
from .config import fields, text
from .runtime import remaining


def relative(value):
    path = PurePosixPath(text(value, "offline input path"))
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts) or str(path) != value:
        raise ValueError("offline inputs require canonical relative paths")
    return path


class Inputs:
    """Read only declared, bounded local files beneath the pinned manifest."""

    def __init__(self, root, policy):
        self.root, self.policy, self.files = root.resolve(), policy, {}

    def path(self, value):
        path = self.root.joinpath(*relative(value).parts)
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("offline input cannot escape its manifest directory")
        return path

    def read(self, asset):
        fields(asset, {"path", "sha256", "bytes"}, "offline asset")
        _sha(asset["sha256"])
        if type(asset["bytes"]) is not int or not 0 < asset["bytes"] <= self.policy["max_unpacked_bytes"]:
            raise ValueError("offline input exceeds its declared byte budget")
        previous = self.files.setdefault(asset["path"], asset)
        if previous != asset or sum(row["bytes"] for row in self.files.values()) > self.policy["max_unpacked_bytes"]:
            raise ValueError("offline inputs conflict or exceed the total byte budget")
        path = self.path(asset["path"])
        if not path.is_file() or path.stat().st_size != asset["bytes"]:
            raise ValueError("offline input differs from its declared byte count")
        with path.open("rb") as stream:
            body = stream.read(asset["bytes"] + 1)
        if len(body) != asset["bytes"] or hashlib.sha256(body).hexdigest() != asset["sha256"]:
            raise ValueError("offline input differs from its pinned content digest")
        return body


def load_manifest(path, expected, policy):
    _sha(expected)
    if path.is_symlink() or path.stat().st_size > policy["max_line_bytes"]:
        raise ValueError("offline provenance manifest exceeds its metadata budget")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("offline provenance manifest differs from its explicit digest pin")
    value = json.loads(body)
    fields(value, {"schema_version", "kind", "original", "candidate", "scope", "inventories", "configuration", "capture", "graphs", "definitions", "core", "timeout_seconds"}, "offline provenance manifest")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["kind"] != "sdmx-native-graph-reprojection":
        raise ValueError("unsupported offline provenance contract")
    if type(value["timeout_seconds"]) is not int or value["timeout_seconds"] <= 0:
        raise ValueError("offline validation requires a positive explicit deadline")
    return value


def tables(path):
    with tarfile.open(path, "r:gz") as archive:
        bodies = {name: archive.extractfile(name).read() for name in (*MEMBERS, "manifest.json")}
    return {name: [json.loads(line) for line in bodies[name].splitlines()] for name in MEMBERS}, json.loads(bodies["manifest.json"]), bodies


def inspect_inputs(path, expected, policy, *, now):
    manifest = load_manifest(path, expected, policy)
    inputs = Inputs(path.parent, policy)
    for name in ("original", "candidate", "scope", "inventories"):
        inputs.read(manifest[name])
    specification = json.loads(inputs.read(manifest["scope"]))
    inventories = json.loads(inputs.read(manifest["inventories"]))
    verify_inventory_scope(specification, inventories)
    archives = {name: inputs.path(manifest[name]["path"]) for name in ("original", "candidate")}
    reports = {name: inspect_availability(archive, policy) for name, archive in archives.items()}
    for name, archive in archives.items():
        verify_build(archive, reports[name], specification, policy)
    original, old_time, old_bytes = tables(archives["original"])
    candidate, new_time, new_bytes = tables(archives["candidate"])
    if any(old_bytes[name] != new_bytes[name] for name in ("partitions.jsonl", "combinations.jsonl")):
        raise ValueError("offline reconstruction changed original partitions or observation combinations")
    if {key: value for key, value in old_time.items() if key != "taken_at"} != {key: value for key, value in new_time.items() if key != "taken_at"}:
        raise ValueError("offline reconstruction changed the archive contract or table counts")
    if not _time(old_time["taken_at"]) <= _time(new_time["taken_at"]) <= now:
        raise ValueError("offline candidate assembly clock is inconsistent")
    definitions = manifest["definitions"]
    if not isinstance(definitions, list) or not definitions:
        raise ValueError("offline provenance requires exact dataset definitions")
    expected_definitions = {}
    for row in definitions:
        fields(row, {"provider", "dataset_id", "original", "candidate"}, "offline definition")
        for name in ("original", "candidate"):
            _sha(row[name])
        key = (text(row["provider"], "provider"), text(row["dataset_id"], "dataset"))
        if key in expected_definitions or row["original"] == row["candidate"]:
            raise ValueError("offline definitions must identify distinct changed datasets")
        expected_definitions[key] = row
    old_datasets = {(row["provider"], row["dataset_id"]): row for row in original["datasets.jsonl"]}
    new_datasets = {(row["provider"], row["dataset_id"]): row for row in candidate["datasets.jsonl"]}
    if old_datasets.keys() != new_datasets.keys() or expected_definitions.keys() != new_datasets.keys():
        raise ValueError("offline definitions omit or add indexed datasets")
    for key, row in new_datasets.items():
        previous = old_datasets[key]
        if {name for name in previous.keys() | row.keys() if previous.get(name) != row.get(name)} != {"definition_sha256"}:
            raise ValueError("offline reconstruction changed source clocks, lifetime or dataset scope")
        if (previous["definition_sha256"] != expected_definitions[key]["original"]
                or row["definition_sha256"] != expected_definitions[key]["candidate"]):
            raise ValueError("offline index definition differs from its explicit declaration")
        if not _time(row["verified_at"]) <= now < _time(row["valid_until"]):
            raise ValueError("offline source evidence is expired or not yet valid")
    graphs = {}
    if not isinstance(manifest["graphs"], list):
        raise TypeError("offline graphs must be an explicit list")
    for row in manifest["graphs"]:
        fields(row, {"provider", "dataset_id", "receipt", "body"}, "offline graph")
        key = (text(row["provider"], "provider"), text(row["dataset_id"], "dataset"))
        if key in graphs or key not in new_datasets:
            raise ValueError("offline graph identity is repeated or outside the index")
        receipt = json.loads(inputs.read(row["receipt"]))
        fields(receipt, {"case", "method", "url", "observed_at", "status", "content_type", "bytes", "sha256"}, "native graph receipt")
        for name in ("case", "url", "content_type"):
            text(receipt[name], f"native graph {name}")
        body = inputs.read(row["body"])
        if (receipt["method"] != "GET" or type(receipt["status"]) is not int or receipt["status"] != 200
                or type(receipt["bytes"]) is not int or receipt["bytes"] != len(body) or receipt["sha256"] != row["body"]["sha256"]):
            raise ValueError("native graph body differs from its successful original receipt")
        if not _time(new_datasets[key]["verified_at"]) <= _time(receipt["observed_at"]) <= _time(new_time["taken_at"]):
            raise ValueError("native graph clock is outside the preserved evidence lifetime and assembly")
        graphs[key] = {"receipt": receipt, "body": body}
    if graphs.keys() != new_datasets.keys():
        raise ValueError("offline provenance omits a native graph")
    return {"manifest": manifest, "inputs": inputs, "specification": specification, "inventories": inventories,
            "report": reports["candidate"], "datasets": new_datasets, "graphs": graphs, "tables": candidate,
            "old_manifest": old_time, "new_manifest": new_time}


def core_identity(root, declaration):
    fields(declaration, {"revision", "files"}, "offline core")
    revision = text(declaration["revision"], "offline core revision")
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("offline core requires an exact commit identity")
    actual_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    if actual_revision != revision:
        raise ValueError("offline validation core commit differs from its declaration")
    files = declaration["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("offline validation requires the complete core Python file manifest")
    for name, sha in files.items():
        relative(name)
        _sha(sha)
    tree = subprocess.run(["git", "ls-tree", "-rz", revision, "--", "server/sdg"], cwd=root, check=True, capture_output=True).stdout
    objects = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        if name.endswith(b".py"):
            objects[name.decode().removeprefix("server/sdg/")] = metadata.split()[2]
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=root, check=True, capture_output=True,
                            input=b"".join(sha + b"\n" for sha in objects.values()))
    stream, committed = io.BytesIO(result.stdout), {}
    for name, sha in objects.items():
        header = stream.readline().split()
        if len(header) != 3 or header[:2] != [sha, b"blob"]:
            raise ValueError("offline core revision contains an invalid Python object")
        committed[name] = hashlib.sha256(stream.read(int(header[2]))).hexdigest()
        if stream.read(1) != b"\n":
            raise ValueError("offline core revision object is incomplete")
    if stream.read() or committed != files:
        raise ValueError("offline core file manifest differs from the declared commit blobs")
    actual = {str(path.relative_to(root / "server/sdg")): digest(path) for path in sorted((root / "server/sdg").rglob("*.py"))}
    if actual != files:
        raise ValueError("offline validation core files differ from the declared implementation")
    return {"revision": revision, "files": actual}


def imported_core_files(core_root, files, modules):
    imported = {}
    for module_name, module in modules.items():
        if module_name != "sdg" and not module_name.startswith("sdg."):
            continue
        filename = getattr(module, "__file__", None)
        if not filename or not Path(filename).resolve().is_relative_to((core_root / "server/sdg").resolve()):
            raise ValueError("offline projection imported an SDG module outside the declared core")
        name = str(Path(filename).resolve().relative_to((core_root / "server/sdg").resolve()))
        if name not in files or digest(Path(filename)) != files[name]:
            raise ValueError("offline projection imported an undeclared core implementation")
        imported[name] = files[name]
    return imported


def runtime_identity(core_root, revision):
    from lxml import etree

    lock = core_root / "server/uv.lock"
    committed = subprocess.run(["git", "show", f"{revision}:server/uv.lock"], cwd=core_root, check=True, capture_output=True).stdout
    sha = hashlib.sha256(committed).hexdigest()
    if digest(lock) != sha:
        raise ValueError("offline core lockfile differs from its declared commit")
    return {"python": sys.version, "implementation": sys.implementation.name,
            "packages": {name: importlib.metadata.version(name) for name in ("lxml", "pydantic", "pydantic-core", "PyYAML", "httpx")},
            "libxml": list(etree.LIBXML_VERSION), "libxslt": list(etree.LIBXSLT_VERSION),
            "project_lockfile": {"path": "server/uv.lock", "sha256": sha},
            "scope": "Observed local runtime; source and lockfile hashes do not certify another environment"}


def verify(path, expected, policy, core_root, *, now):
    state = inspect_inputs(path, expected, policy, now=now)
    core = core_identity(core_root, state["manifest"]["core"])
    from .availability_sdmx import project

    projected = project(state, core_root)
    if core_identity(core_root, state["manifest"]["core"]) != core:
        raise ValueError("offline core changed during verification")
    for asset in list(state["inputs"].files.values()):
        state["inputs"].read(asset)
    if digest(path) != expected:
        raise ValueError("offline manifest changed during verification")
    imported = imported_core_files(core_root, core["files"], dict(sys.modules))
    return {"schema_version": 1, "kind": state["manifest"]["kind"], "verified_at": now.isoformat(),
            "provenance_sha256": expected, "archive": state["manifest"]["candidate"],
            "original": state["manifest"]["original"], "core": core, "imported_core_files": imported,
            "runtime": runtime_identity(core_root, core["revision"]),
            "publisher_files": {str(p.relative_to(Path(__file__).parent)): digest(p) for p in sorted(Path(__file__).parent.rglob("*.py"))},
            "inputs": state["inputs"].files, "graphs": [{"provider": key[0], "dataset_id": key[1], "receipt": value["receipt"]} for key, value in state["graphs"].items()],
            "definitions": state["manifest"]["definitions"], "projection": projected,
            "source_clocks_unchanged": True, "ttl_renewed": False, "source_requests": 0,
            "report": state["report"], "scope": state["specification"], "inventories": state["inventories"],
            "source_bodies_published": False}


def validate(config, path, expected, policy_path):
    policy = policy_from(policy_path)
    manifest = load_manifest(path, expected, policy)
    root = Path(__file__).resolve().parents[1]
    deployment = config["deployment"]
    command = [str(deployment["python"]), "-B", "-m", "catalogue.availability_offline", "--manifest", str(path.resolve()),
               "--sha256", expected, "--policy", str(policy_path.resolve()), "--core", str(deployment["harvester"])]
    result = subprocess.run(command, cwd=root, env={**os.environ, "PYTHONPATH": os.pathsep.join((str(root), str(deployment["harvester"] / "server")))},
                            check=True, capture_output=True, text=True, timeout=remaining(config, manifest["timeout_seconds"]))
    proof = json.loads(result.stdout)
    if proof["provenance_sha256"] != expected or proof["archive"] != manifest["candidate"] or proof["core"] != manifest["core"]:
        raise ValueError("offline validator returned evidence for different inputs or core")
    return proof


def prepare(config, path, expected, policy_path, directory, destination, template_path):
    from .availability_publish import prepare as publication

    proof = validate(config, path, expected, policy_path)
    source = directory / "offline-source"
    source.mkdir(exist_ok=False)
    inputs = Inputs(path.parent, policy_from(policy_path))
    body = inputs.read(proof["archive"])
    (source / "availability.tar.gz").write_bytes(body)
    for name, value in (("quality.json", proof["report"]), ("scope.json", proof["scope"]), ("inventories.json", proof["inventories"])):
        (source / name).write_text(json.dumps(value), encoding="utf-8")
    provenance_path = source / "offline-provenance.json"
    provenance_path.write_text(json.dumps(proof, sort_keys=True, indent=2), encoding="utf-8")
    (source / "input-manifest.json").write_bytes(path.read_bytes())
    if digest(source / "input-manifest.json") != expected:
        raise ValueError("offline input manifest changed before publication staging")
    return publication(source, directory, destination, policy_path, template_path,
                       now=datetime.now(UTC), provenance_sha256=digest(provenance_path))


def publish(config, path, expected, policy_path, directory, destination, template_path):
    from .publish import upload_files

    report, files = prepare(config, path, expected, policy_path, directory, destination, template_path)
    return upload_files(directory, config, files, f"{destination}/availability.tar.gz", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    args = parser.parse_args()

    def local_only(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("offline provenance validation forbids network and database connections")

    sys.addaudithook(local_only)
    print(json.dumps(verify(args.manifest, args.sha256, policy_from(args.policy), args.core, now=datetime.now(UTC))))


if __name__ == "__main__":
    main()
