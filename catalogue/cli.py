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

from .archive import QualityError, inspect_archive
from .availability import inspect_availability, policy_from
from .config import load
from .discovery import prepare
from .publish import upload
from .runtime import remaining


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
        timeout=remaining(config),
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
        "StandardOutPath": str(settings["log"]),
        "StandardErrorPath": str(settings["log"]),
    }
    if settings["action"] == "run-update":
        from datetime import UTC, datetime

        from .update_plan import load as load_plan
        from .update_run import require_initial_coverage

        plan = load_plan(settings["plan"], config)
        if settings["interval_seconds"] != plan["cadence"]["interval_seconds"]:
            raise ValueError("schedule interval must match the update plan's freshness budget")
        require_initial_coverage(plan, config, now=datetime.now(UTC), run_at_load=settings["run_at_load"])
        payload["ProgramArguments"].extend(("--plan", str(settings["plan"])))
        payload["StartInterval"] = settings["interval_seconds"]
        payload["RunAtLoad"] = settings["run_at_load"]
    else:
        payload["StartCalendarInterval"] = {
            "Weekday": settings["weekday"], "Hour": settings["hour"], "Minute": settings["minute"],
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
    verify_catalogue_command = commands.add_parser(
        "verify-catalogue", help="record a new immutable discovery readback; no upload or quality waiver"
    )
    verify_catalogue_command.add_argument("--archive", type=Path, required=True)
    verify_catalogue_command.add_argument("--revision", required=True)
    verify_catalogue_command.add_argument("--expect-sha256", required=True)
    verify_catalogue_command.add_argument("--expect-bytes", type=int, required=True)
    verify_catalogue_command.add_argument("--output", type=Path, required=True)
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
    build_availability.add_argument("--capture", type=Path)
    build_availability.add_argument("--capture-manifest", type=Path)
    build_availability.add_argument("--capture-sha256")
    build_availability.add_argument("--inventory-evidence", type=Path)
    build_availability.add_argument("--inventory-sha256")
    build_availability.add_argument("--snapshot-provider", action="append", default=[])
    build_availability.add_argument("--snapshot-shard-prefix-length", type=int)
    snapshots = commands.add_parser("publish-snapshots", help="validate and publish licensed immutable source projections")
    snapshots.add_argument("--directory", type=Path, required=True)
    snapshots.add_argument("--availability", type=Path, required=True)
    snapshots.add_argument("--destination", required=True)
    snapshots.add_argument("--policy", type=Path, required=True)
    publish_availability = commands.add_parser(
        "publish-availability", help="revalidate and publish a completed index in its own repository directory"
    )
    publish_availability.add_argument("--directory", type=Path, required=True)
    publish_availability.add_argument("--destination", required=True)
    publish_availability.add_argument("--policy", type=Path, required=True)
    publish_availability.add_argument("--readme-template", type=Path, required=True)
    activate_availability = commands.add_parser(
        "activate-availability", help="verify and activate a published index in the configured SDG deployment"
    )
    activate_availability.add_argument("--publication", type=Path, required=True)
    activate_availability.add_argument("--index", required=True)
    activate_availability.add_argument("--expect-sha256", required=True)
    activate_availability.add_argument("--snapshot-publications", type=Path)
    documentation = commands.add_parser("publish-documentation", help="verify published bytes and update the Hub card without replacing archives")
    documentation.add_argument("--catalogue-archive", type=Path, required=True)
    documentation.add_argument("--catalogue-revision", required=True)
    documentation.add_argument("--availability-releases", type=Path, required=True)
    documentation.add_argument("--readme-template", type=Path, required=True)
    documentation.add_argument("--viewer-config", type=Path, required=True)
    for name in ("prepare", "refresh", "publish", "release"):
        commands.add_parser(name)
    for name, help_text in (
        ("check-update", "validate an explicit update plan and its current deployment state; no source reads or uploads"),
        ("run-update", "build, publish, activate and document an explicit update plan"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--plan", type=Path, required=True)
    scheduled = commands.add_parser(
        "schedule", help="write a launchd plist without installing or starting it"
    )
    scheduled.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config_path = args.config.resolve()
        config = load(config_path)
        if args.command == "verify-catalogue":
            from .receipts import verify_catalogue

            print(json.dumps(verify_catalogue(config, args.archive, args.revision, args.expect_sha256,
                                             args.expect_bytes, args.output), indent=2))
            return 0
        if args.command in {"check-update", "run-update"}:
            from .update_plan import load as load_plan
            from .update_plan import load_state
            from .update_run import preflight, run

            plan = load_plan(args.plan.resolve(), config)
            with publication_lock(config["deployment"]["build"]):
                if args.command == "check-update":
                    state, _ = load_state(Path(plan["state"]), config)
                    preflight(state, config, harvester)
                    result = {"valid": True, "updated_indexes": list(plan["indexes"]), "cadence": plan["cadence"], "uploaded": False}
                else:
                    directory = Path(tempfile.mkdtemp(prefix="update-", dir=config["deployment"]["build"]))
                    print(f"update directory: {directory}", file=sys.stderr, flush=True)
                    result = run(directory, config, plan, harvester, prepare)
                print(json.dumps(result, indent=2))
            return 0
        if args.command == "activate-availability":
            source_arguments = ["--snapshot-publications", str(args.snapshot_publications.resolve())] if args.snapshot_publications is not None else []
            with publication_lock(config["deployment"]["build"]):
                result = json.loads(harvester(
                    config, "activate-availability", "--index", args.index, "--publication", str(args.publication.resolve()),
                    "--expect-sha256", args.expect_sha256, *source_arguments, capture=True,
                ))
                if not isinstance(result, dict) or result.get("activated") is not True:
                    raise ValueError("consumer did not confirm availability activation")
                directory = Path(tempfile.mkdtemp(prefix="activation-", dir=config["deployment"]["build"]))
                (directory / "activation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(json.dumps({"directory": str(directory), **result}, indent=2))
            return 0
        if args.command == "publish-documentation":
            from .documentation import prepare as prepare_documentation
            from .documentation import publish as publish_documentation
            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="documentation-", dir=config["deployment"]["build"]))
                print(f"documentation directory: {directory}", file=sys.stderr, flush=True)
                prepare_documentation(directory, config, args.catalogue_archive, args.catalogue_revision,
                                      args.availability_releases, args.readme_template,
                                      args.viewer_config)
                print(json.dumps(publish_documentation(directory, config), indent=2))
            return 0
        if args.command == "publish-snapshots":
            from .snapshots import publish
            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="snapshots-publication-", dir=config["deployment"]["build"]))
                print(f"publication directory: {directory}", file=sys.stderr, flush=True)
                print(json.dumps(publish(args.directory, args.availability, directory, args.destination, config, args.policy), indent=2))
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

            captured = {"directory": args.capture, "manifest": args.capture_manifest, "sha256": args.capture_sha256,
                        "inventory_evidence": args.inventory_evidence, "inventory_sha256": args.inventory_sha256}
            if any(value is not None for value in captured.values()) and not all(value is not None for value in captured.values()):
                raise ValueError("captured-source builds require response directory, manifest, inventory evidence and both digest pins")
            with publication_lock(config["deployment"]["build"]):
                directory = Path(tempfile.mkdtemp(prefix="availability-", dir=config["deployment"]["build"]))
                report = prepare_availability(directory, config, args.scope, args.policy, harvester,
                                              capture=captured if args.capture is not None else None,
                                              snapshot_providers=args.snapshot_provider, snapshot_shard_prefix_length=args.snapshot_shard_prefix_length)
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
            report = prepare(directory, config, harvester)
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
