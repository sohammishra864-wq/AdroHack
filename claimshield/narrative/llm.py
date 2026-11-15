"""Background LLM polish of the template narrative. The template is shown first; the LLM text
replaces it only if it lands within thresholds.narrative.llm_swap_timeout_s AND keeps every
number and placeholder exactly (an LLM never produces or adjusts a number).
"""
from __future__ import annotations

import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from .. import config, llm

SYSTEM = ("You rewrite fraud-check notes for an insurance adjuster in plain, calm English. "
          "Use only the facts given. Keep every number and every [PLACEHOLDER] exactly as "
          "written. Do not add facts, scores, advice or numbers. At most 120 words.")
NUM = re.compile(r"\d+(?:[.,]\d+)*")
PH = re.compile(r"\[[A-Z]+_\d+\]")
_pool = ThreadPoolExecutor(max_workers=2)


def faithful(template: str, out: str) -> bool:
    """Every number / placeholder in the output also appears in the template, and every
    placeholder of the template survives."""
    return (set(NUM.findall(out)) <= set(NUM.findall(template))
            and set(PH.findall(out)) == set(PH.findall(template)))


def _call(template: str) -> str | None:
    out = llm.complete(SYSTEM, template, timeout=config.cfg("thresholds")["narrative"]["llm_swap_timeout_s"] * 2)
    return out.strip() if out and faithful(template, out) else None


def start(template: str) -> tuple[Future, float]:
    """Fire the rewrite in the background. `template` must already be scrubbed."""
    return _pool.submit(_call, template), time.perf_counter()


def result(job: tuple[Future, float]) -> str | None:
    """The rewrite if it arrives within the swap window (counted from start()), else None."""
    fut, t0 = job
    left = config.cfg("thresholds")["narrative"]["llm_swap_timeout_s"] - (time.perf_counter() - t0)
    try:
        return fut.result(timeout=max(0.0, left))
    except FutureTimeout:
        return None
