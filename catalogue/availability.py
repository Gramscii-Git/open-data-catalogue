"""Validate joint availability artifacts without loading their combinations into RAM."""

import hashlib
import json
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import tomllib

from .archive import digest
from .config import fields, strings, text

MEMBERS = ("datasets.jsonl", "partitions.jsonl", "combinations.jsonl")


def policy_from(path: Path) -> dict:
    policy = tomllib.loads(path.read_text(encoding="utf-8"))
    fields(
        policy,
        {
            "schema",
            "providers",
            "staging_directory",
            "max_unpacked_bytes",
            "max_line_bytes",
            "max_rows",
            "max_database_bytes",
        },
        "availability policy",
    )
    if type(policy["schema"]) is not int or policy["schema"] != 1:
        raise ValueError("availability policy schema must be 1")
    policy["providers"] = strings(policy["providers"], "availability providers")
    if len(set(policy["providers"])) != len(policy["providers"]):
        raise ValueError("availability providers must be distinct")
    for name in (
        "max_unpacked_bytes",
        "max_line_bytes",
        "max_rows",
        "max_database_bytes",
    ):
        if type(policy[name]) is not int or policy[name] <= 0:
            raise ValueError(f"availability {name} must be a positive integer")
    if policy["max_line_bytes"] > policy["max_unpacked_bytes"]:
        raise ValueError("availability line limit exceeds the unpacked byte limit")
    policy["staging_directory"] = (
        path.parent
        / text(policy["staging_directory"], "availability staging directory")
    ).resolve()
    return policy


def _sha(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("availability evidence requires a SHA-256 digest")


def _time(value):
    parsed = datetime.fromisoformat(text(value, "availability timestamp"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("availability timestamps require a timezone")
    return parsed


def _instant(value):
    return _time(value).astimezone(UTC).isoformat(timespec="microseconds")


def _key(row):
    return json.dumps(
        [text(row["provider"], "provider"), text(row["dataset_id"], "dataset")]
    )


def _dataset(conn, row, policy):
    fields(
        row,
        {
            "provider",
            "dataset_id",
            "title",
            "scope",
            "definition_sha256",
            "period_kind",
            "axes",
            "partitions",
            "verified_at",
            "valid_until",
        },
        "availability dataset",
    )
    if row["provider"] not in policy["providers"]:
        raise ValueError("availability dataset has no declared provider policy")
    text(row["title"], "dataset title")
    if not isinstance(row["scope"], dict) or not row["scope"]:
        raise ValueError("availability dataset requires an explicit indexing scope")
    _sha(row["definition_sha256"])
    if row["period_kind"] not in {"calendar", "snapshot", "source-label"}:
        raise ValueError("availability dataset requires declared period semantics")
    if _time(row["verified_at"]) >= _time(row["valid_until"]):
        raise ValueError("availability evidence expires before verification")
    axes = strings(row["axes"], "availability axes")
    if len(axes) != len(set(axes)):
        raise ValueError("availability axes must be distinct")
    partitions = strings(row["partitions"], "expected indexing partitions")
    if len(partitions) != len(set(partitions)):
        raise ValueError("expected indexing partitions must be distinct")
    for identity in partitions:
        _sha(identity)
    conn.execute(
        "INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _key(row),
            row["provider"],
            json.dumps(sorted(axes)),
            len(partitions),
            row["period_kind"],
            _instant(row["verified_at"]),
            _instant(row["valid_until"]),
            json.dumps(row["scope"], sort_keys=True),
        ),
    )
    conn.executemany(
        "INSERT INTO expected VALUES (?, ?)",
        ((_key(row), identity) for identity in partitions),
    )


def _partition(conn, row, policy):
    fields(
        row,
        {"provider", "dataset_id", "id", "complete", "request", "receipts"},
        "availability partition",
    )
    if row["complete"] is not True:
        raise ValueError("an incomplete indexing partition cannot be published")
    if not isinstance(row["request"], dict) or not row["request"]:
        raise ValueError("indexing partitions require their native request")
    if (
        row["id"]
        != hashlib.sha256(
            json.dumps(row["request"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise ValueError(
            "indexing partition identity does not match its declared request"
        )
    receipts = row["receipts"]
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("indexing partitions require source read receipts")
    observed = []
    for receipt in receipts:
        fields(
            receipt,
            {
                "method",
                "url",
                "request_sha256",
                "status",
                "bytes",
                "wire_bytes",
                "sha256",
                "observed_at",
                "etag",
                "last_modified",
            },
            "source receipt",
        )
        if (
            receipt["method"] not in {"GET", "POST"}
            or type(receipt["status"]) is not int
            or receipt["status"] != 200
        ):
            raise ValueError("only successful source reads establish availability")
        url = urlsplit(text(receipt["url"], "receipt URL"))
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
        ):
            raise ValueError(
                "published availability receipts require HTTPS without credentials"
            )
        for name in ("bytes", "wire_bytes"):
            if type(receipt[name]) is not int or receipt[name] < 0:
                raise ValueError(
                    "source receipt byte counts must be non-negative integers"
                )
        for name in ("sha256", "request_sha256"):
            _sha(receipt[name])
        observed.append(_instant(receipt["observed_at"]))
        for name in ("etag", "last_modified"):
            if receipt[name] is not None:
                text(receipt[name], name)
    conn.execute(
        "INSERT INTO partitions VALUES (?, ?, ?, ?)",
        (
            _key(row),
            text(row["id"], "partition identity"),
            min(observed),
            max(observed),
        ),
    )


def _combination(conn, row, policy):
    fields(
        row,
        {
            "provider",
            "dataset_id",
            "partition",
            "period",
            "territory",
            "dimensions",
            "presence",
        },
        "availability combination",
    )
    period, territory, dimensions = row["period"], row["territory"], row["dimensions"]
    fields(period, {"id", "label", "start", "end"}, "observation period")
    fields(territory, {"code", "label", "level"}, "observation territory")
    if (period["start"] is None) != (period["end"] is None):
        raise ValueError("availability period requires both bounds or neither")
    if period["start"] is not None and _time(period["start"]) > _time(period["end"]):
        raise ValueError("availability period starts after it ends")
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValueError("availability combination requires dimension identities")
    for name, choice in dimensions.items():
        text(name, "dimension identity")
        fields(choice, {"code", "label"}, "dimension choice")
        text(choice["code"], "dimension code")
        text(choice["label"], "dimension label")
    for value in (period["label"], territory["label"], territory["level"]):
        text(value, "source label")
    if row["presence"] not in {"observed", "missing", "suppressed"}:
        raise ValueError(
            "availability combination requires explicit observation presence"
        )
    identity = json.dumps(
        {
            "period": text(period["id"], "period identity"),
            "territory": text(territory["code"], "territory identity"),
            "level": territory["level"],
            "dimensions": {key: value["code"] for key, value in dimensions.items()},
        },
        sort_keys=True,
    )
    conn.execute(
        "INSERT INTO combinations VALUES (?, ?, ?, ?, ?)",
        (
            _key(row),
            text(row["partition"], "partition identity"),
            hashlib.sha256(identity.encode()).hexdigest(),
            json.dumps(sorted(dimensions)),
            period["start"] is not None,
        ),
    )


def inspect_availability(path: Path, policy: dict) -> dict:
    policy["staging_directory"].mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="availability-", dir=policy["staging_directory"]
    ) as staging:
        conn = sqlite3.connect(Path(staging) / "validation.sqlite")
        try:
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            pages = policy["max_database_bytes"] // page_size
            if pages <= 0:
                raise ValueError(
                    "availability database budget is smaller than one SQLite page"
                )
            conn.execute(f"PRAGMA max_page_count = {pages}")
            conn.executescript(
                "CREATE TABLE datasets (id TEXT PRIMARY KEY, provider TEXT, axes TEXT, partitions INTEGER, period_kind TEXT, verified_at TEXT, valid_until TEXT, scope TEXT);"
                "CREATE TABLE expected (dataset TEXT, id TEXT, PRIMARY KEY(dataset, id));"
                "CREATE TABLE partitions (dataset TEXT, id TEXT, first_read TEXT, last_read TEXT, PRIMARY KEY(dataset, id));"
                "CREATE TABLE combinations (dataset TEXT, partition TEXT, id TEXT, axes TEXT, bounded INTEGER, PRIMARY KEY(dataset, id));"
            )
            report = _inspect(path, policy, conn)
        finally:
            conn.close()
    return {**report, "sha256": digest(path), "bytes": path.stat().st_size}


def _inspect(path, policy, conn):
    counts, unpacked, seen, manifest = {}, 0, set(), None
    readers = dict(zip(MEMBERS, (_dataset, _partition, _combination), strict=True))
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if (
                member.name not in {*MEMBERS, "manifest.json"}
                or member.name in seen
                or not member.isfile()
            ):
                raise ValueError(
                    "availability archive has an unknown, repeated or non-file member"
                )
            seen.add(member.name)
            unpacked += member.size
            if unpacked > policy["max_unpacked_bytes"]:
                raise ValueError(
                    "availability archive exceeds its unpacked byte budget"
                )
            stream = archive.extractfile(member)
            count = 0
            while line := stream.readline(policy["max_line_bytes"] + 1):
                if len(line) > policy["max_line_bytes"]:
                    raise ValueError("availability record exceeds its line byte budget")
                row = json.loads(line)
                if member.name == "manifest.json":
                    if manifest is not None:
                        raise ValueError(
                            "availability manifest must be one JSON record"
                        )
                    manifest = row
                else:
                    readers[member.name](conn, row, policy)
                count += 1
                if count + sum(counts.values()) > policy["max_rows"]:
                    raise ValueError("availability archive exceeds its record budget")
            counts[member.name] = count
    if seen != {*MEMBERS, "manifest.json"}:
        raise ValueError(
            "availability archive requires its manifest and all three tables"
        )
    fields(manifest, {"schema_version", "taken_at", "tables"}, "availability manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("availability archive schema must be 1")
    taken_at = _instant(manifest["taken_at"])
    fields(manifest["tables"], MEMBERS, "availability table counts")
    for name in MEMBERS:
        if (
            type(manifest["tables"][name]) is not int
            or manifest["tables"][name] != counts[name]
        ):
            raise ValueError("availability manifest counts do not match its tables")
    providers = {
        row[0] for row in conn.execute("SELECT DISTINCT provider FROM datasets")
    }
    if providers != set(policy["providers"]):
        raise ValueError("availability artifact does not cover its required providers")
    if (
        conn.execute(
            "SELECT 1 FROM datasets d WHERE d.valid_until <= ? OR d.verified_at > ? "
            "OR d.verified_at != (SELECT min(p.first_read) FROM partitions p WHERE p.dataset = d.id) LIMIT 1",
            (taken_at, taken_at),
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM partitions WHERE last_read > ? LIMIT 1",
            (taken_at,),
        ).fetchone()
    ):
        raise ValueError(
            "availability timestamps conflict with source receipts or expire before the snapshot"
        )
    if conn.execute(
        "SELECT 1 FROM datasets d WHERE d.partitions != (SELECT count(*) FROM partitions p WHERE p.dataset = d.id) "
        "OR NOT EXISTS (SELECT 1 FROM combinations c WHERE c.dataset = d.id) LIMIT 1"
    ).fetchone():
        raise ValueError(
            "availability dataset has incomplete partitions or no verified combinations"
        )
    if (
        conn.execute(
            "SELECT 1 FROM partitions p LEFT JOIN expected e ON e.dataset = p.dataset AND e.id = p.id "
            "WHERE e.id IS NULL LIMIT 1"
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM combinations c LEFT JOIN partitions p ON p.dataset = c.dataset AND p.id = c.partition "
            "LEFT JOIN datasets d ON d.id = c.dataset WHERE p.id IS NULL OR d.id IS NULL OR c.axes != d.axes "
            "OR (d.period_kind != 'source-label' AND c.bounded = 0) LIMIT 1"
        ).fetchone()
    ):
        raise ValueError(
            "availability combination has an invalid partition, dimension set or period"
        )
    return {
        "manifest": manifest,
        "datasets": [
            {
                "provider": json.loads(key)[0], "dataset_id": json.loads(key)[1], "scope": json.loads(scope),
                "partitions": [row[0] for row in conn.execute("SELECT id FROM expected WHERE dataset = ? ORDER BY id", (key,))],
            }
            for key, scope in conn.execute("SELECT id, scope FROM datasets ORDER BY id")
        ],
        "tables": {name: counts[name] for name in MEMBERS},
        "unpacked_bytes": unpacked,
    }
