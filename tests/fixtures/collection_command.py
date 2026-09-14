"""Exercise the collector's native child-command boundary without provider access."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", type=Path, required=True)
parser.add_argument("step", choices=("sync", "structure"))
parser.add_argument("--provider", required=True)
parser.add_argument("--retry-policy", type=Path, required=True)
parser.add_argument("--patience", type=float)
args = parser.parse_args()
configuration = json.loads(args.env_file.read_text())
with Path(configuration["calls"]).open("a") as stream:
    stream.write(json.dumps({"step": args.step, "provider": args.provider,
                             "retry_policy": str(args.retry_policy), "patience": args.patience}) + "\n")
if args.step == "structure" and Path(configuration["failure"]).exists():
    raise SystemExit(7)

