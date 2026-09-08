"""Explicit preparation, validation, publication and schedule generation."""

import argparse
import json
import os
import plistlib
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from string import Template

from .archive import QualityError, inspect_archive
from .availability import inspect_availability, policy_from
from .config import load
from .publish import upload


def harvester(config, *arguments, capture=False):
    deployment = config["deployment"]
    server = deployment["harvester"] / "server"
    environment = deployment["environment_file"]
    if not environment.is_file():
        raise ValueError(f"harvester configuration is missing: {environment}")
    result = subprocess.run(
        [str(deployment["python"]), "-B", "-m", "sdg.plugins.opendata", "--env-file", str(environment), *arguments],
        cwd=server,
        env={**os.environ, "PYTHONPATH": str(server)},
        stdout=subprocess.PIPE if capture else None,
        text=True,
        check=True,
    )
    return result.stdout


@contextmanager
def publication_lock(build: Path):
    build.mkdir(parents=True, exist_ok=True)
    lock = build / ".publisher.lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise RuntimeError(
            f"publisher lock exists: {lock}; inspect the owning process before removing a stale lock"
        ) from error
    try:
        yield
    finally:
        lock.rmdir()


def dataset_readme(template_path: Path, config: dict, report: dict) -> str:
    template = Template(template_path.read_text(encoding="utf-8"))
    values = {
        "taken_at": report["manifest"]["taken_at"],
        "table_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["tables"].items()
        ),
        "provider_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["providers"].items()
        ),
        "quality_rows": "\n".join(
            f"| {key} | {value} |" for key, value in report["metrics"].items()
        ),
        "archive": config["hub"]["archive"],
        "sha256": report["sha256"],
        "bytes": str(report["bytes"]),
    }
    if not template.is_valid() or set(template.get_identifiers()) != set(values):
        raise ValueError(
            "dataset README template must declare every release placeholder exactly by name"
        )
    return template.substitute(values)


def prepare(directory: Path, config: dict) -> dict:
    archive = directory / config["hub"]["archive"]
    exported = json.loads(
        harvester(config, "export", "--to", str(archive), capture=True)
    )
    try:
        report = inspect_archive(archive, config["quality"])
    except QualityError as error:
        (directory / "quality.json").write_text(
            json.dumps(error.report, indent=2), encoding="utf-8"
        )
        raise
    if (
        exported["sha256"] != report["sha256"]
        or exported["bytes"] != report["bytes"]
        or exported["tables"] != report["tables"]
    ):
        raise ValueError("export report does not match the validated archive")
    (directory / "manifest.json").write_text(
        json.dumps(report["manifest"], indent=2), encoding="utf-8"
    )
    (directory / "quality.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (directory / "SHA256SUMS").write_text(
        f"{report['sha256']}  {archive.name}\n", encoding="utf-8"
    )
    (directory / "README.md").write_text(
        dataset_readme(config["deployment"]["readme_template"], config, report),
        encoding="utf-8",
    )
    return report


def schedule(config_path: Path, config: dict, output: Path) -> None:
    settings = config["schedule"]
    payload = {
        "Label": settings["label"],
        "ProgramArguments": [
            str(settings["python"]),
            str(Path(__file__).resolve().parents[1] / "update"),
            "--config",
            str(config_path),
            settings["action"],
        ],
        "WorkingDirectory": str(config_path.parent),
        "EnvironmentVariables": {"PATH": settings["path"]},
        "StartCalendarInterval": {
            "Weekday": settings["weekday"],
            "Hour": settings["hour"],
            "Minute": settings["minute"],
        },
        "StandardOutPath": str(settings["log"]),
        "StandardErrorPath": str(settings["log"]),
    }
    settings["log"].parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        plistlib.dump(payload, stream)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check", help="validate an existing archive; no harvest or upload"
    )
    check.add_argument("--archive", type=Path, required=True)
    availability = commands.add_parser(
        "check-availability",
        help="validate a joint-availability artifact; no source reads or upload",
    )
    availability.add_argument("--archive", type=Path, required=True)
    availability.add_argument("--policy", type=Path, required=True)
    build_availability = commands.add_parser(
        "build-availability", help="construct and verify a declared shared availability scope; no upload"
    )
    build_availability.add_argument("--scope", type=Path, required=True)
    build_availability.add_argument("--policy", type=Path, required=True)
    publish_availability = commands.add_parser(
        "publish-availability", help="revalidate and publish a completed index in its own repository directory"
    )
    publish_availability.add_argument("--directory", type=Path, required=True)
    publish_availability.add_argument("--destination", required=True)
    publish_availability.add_argument("--policy", type=Path, required=True)
    publish_availability.add_argument("--readme-template", type=Path, required=True)
    documentation = commands.add_parser("publish-documentation", help="verify published bytes and update the Hub card without replacing archives")
    documentation.add_argument("--catalogue-archive", type=Path, required=True)
    documentation.add_argument("--catalogue-revision", required=True)
    documentation.add_argument("--availability-archive", type=Path, required=True)
    documentation.add_argument("--availability-revision", required=True)
    documentation.add_argument("--policy", type=Path, required=True)
    documentation.add_argument("--readme-template", type=Path, required=True)
    documentation.add_argument("--viewer-config", type=Path, required=True)
    for name in ("prepare", "refresh", "publish", "release"):
        commands.add_parser(name)
    scheduled = commands.add_parser(
        "schedule", help="write a launchd plist without installing or starting it"
    )
    scheduled.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config_path = args.config.resolve()
        config = load(config_path)
        if args.command == "publish-documentation":
            from .documentation import prepare as prepare_documentation
            from .documentation import publish as publish_documentation
            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="documentation-", dir=config["deployment"]["build"]))
                print(f"documentation directory: {directory}", file=sys.stderr, flush=True)
                prepare_documentation(directory, config, args.catalogue_archive, args.catalogue_revision,
                                      args.availability_archive, args.availability_revision, args.policy, args.readme_template,
                                      args.viewer_config)
                print(json.dumps(publish_documentation(directory, config), indent=2))
            return 0
        if args.command == "publish-availability":
            from .availability_publish import publish
            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="publication-", dir=config["deployment"]["build"]))
                print(f"publication directory: {directory}", file=sys.stderr, flush=True)
                print(json.dumps(publish(
                    args.directory, directory, args.destination, config, args.policy, args.readme_template,
                ), indent=2))
            return 0
        if args.command == "check-availability":
            print(
                json.dumps(
                    inspect_availability(args.archive, policy_from(args.policy)),
                    indent=2,
                )
            )
            return 0
        if args.command == "schedule":
            schedule(config_path, config, args.output)
            print(json.dumps({"schedule": str(args.output), "installed": False}))
            return 0
        if args.command == "check":
            print(
                json.dumps(inspect_archive(args.archive, config["quality"]), indent=2)
            )
            return 0
        if args.command == "build-availability":
            from .availability_build import prepare as prepare_availability

            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="availability-", dir=config["deployment"]["build"]))
                report = prepare_availability(directory, config, args.scope, args.policy, harvester)
            print(json.dumps({"directory": str(directory), "report": report}, indent=2))
            return 0
        with publication_lock(config["deployment"]["build"]):
            contract = harvester(config, "--release-contract", capture=True).strip()
            if contract != "1":
                raise ValueError(
                    "harvester release contract must be 1; update the harvester checkout"
                )
            if args.command in ("refresh", "release"):
                harvester(config, "sync")
                harvester(
                    config,
                    "structure",
                    "--patience",
                    str(config["deployment"]["patience_seconds"]),
                )
                harvester(config, "enrich")
                harvester(config, "verify")
            directory = Path(
                tempfile.mkdtemp(prefix="release-", dir=config["deployment"]["build"])
            )
            print(f"release directory: {directory}", file=sys.stderr, flush=True)
            report = prepare(directory, config)
            if args.command in ("publish", "release"):
                print(json.dumps(upload(directory, config, report), indent=2))
            else:
                print(
                    json.dumps(
                        {
                            "directory": str(directory),
                            "uploaded": False,
                            "quality": report,
                        },
                        indent=2,
                    )
                )
        return 0
    except QualityError as error:
        print(json.dumps(error.report, indent=2), file=sys.stderr)
        return 1
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        sqlite3.Error,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
