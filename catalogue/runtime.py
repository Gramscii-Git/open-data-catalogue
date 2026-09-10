"""Propagate an explicit update-run deadline into subprocesses and readback."""

import time


def remaining(config, requested=None):
    deadline = config.get("run_deadline")
    if deadline is None:
        return requested
    budget = deadline - time.monotonic()
    if budget <= 0:
        raise TimeoutError("update exceeded its configured maximum run duration")
    return budget if requested is None else min(budget, requested)
