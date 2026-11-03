"""A release's series inventory for the test archive's one provider, `sample`: ECB's harvester-written tables and
blocks under sample/, and a manifest naming them with two tables left out."""

import json
import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "series"


def sample_series(target: Path) -> Path:
    shutil.copytree(FIXTURE / "ecb", target / "sample")
    entry = json.loads((FIXTURE / "series-manifest.json").read_bytes())["providers"]["ecb"]
    for part in ("tables", "blocks"):
        entry[part]["file"] = entry[part]["file"].replace("ecb/", "sample/")
    entry["left_out"] = [{"dataset_id": "YC", "reason": "not collected yet"},
                         {"dataset_id": "ZZ", "reason": "HTTP 413 | too large"}]
    (target / "series-manifest.json").write_text(json.dumps({"providers": {"sample": entry}}))
    return target
