"""Expose the native child environment for the publisher process contract."""

import argparse
import json
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", type=Path, required=True)
args = parser.parse_args()
observed = ("DATABASE_URL", "OPENDATA_PACING", "HTTP_HOSTS", "AUTH_TOKEN", "PYTHONPATH", "NATIVE_CONTEXT", "UNDECLARED_PARENT")
print(json.dumps({"environment": {key: os.environ[key] for key in observed if key in os.environ},
                  "environment_keys": sorted(os.environ), "environment_file": str(args.env_file),
                  "file_content": args.env_file.read_text(), "prefix": sys.prefix}))
