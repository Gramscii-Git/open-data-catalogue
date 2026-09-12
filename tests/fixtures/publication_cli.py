"""Exercise the upload command contract against an isolated filesystem Hub."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("action", choices=["upload"])
    parser.add_argument("repository")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", choices=["."])
    parser.add_argument("--repo-type", choices=["dataset"], required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--commit-message", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    parser.add_argument("--include", action="append", required=True)
    args = parser.parse_args()
    payloads = {name: (args.source / name).read_bytes() for name in args.include}
    digest = hashlib.sha1()
    for name, payload in sorted(payloads.items()):
        digest.update(name.encode())
        digest.update(payload)
    revision = digest.hexdigest()
    target = args.root / "datasets" / args.repository / "resolve" / revision
    target.mkdir(parents=True)
    for name in payloads:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.source / name, path)
    with (args.root / "uploads.jsonl").open("a") as stream:
        stream.write(json.dumps({"revision": revision, "files": args.include}) + "\n")
    print(json.dumps({"url": f"{args.endpoint}/datasets/{args.repository}/commit/{revision}"}))


if __name__ == "__main__":
    main()
