"""Text LLM: Bedrock Claude → Qwen (OpenAI-compatible), temperature 0.
CLAIMSHIELD_LLM_PRIMARY = bedrock | qwen | template (template → no call at all).
Callers must pass text that is already PII-scrubbed (narrative/template.scrub).
"""
from __future__ import annotations

import os
from functools import lru_cache

from .. import config  # noqa: F401  (loads .env, so the credentials are there whoever imports this first)


@lru_cache(maxsize=4)
def _bedrock(read_timeout: int = 8):
    import boto3
    from botocore.config import Config

    c = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                     config=Config(read_timeout=read_timeout, connect_timeout=3, retries={"max_attempts": 1}))
    tok = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if tok:  # older boto3 does not pick the bearer token up by itself
        def _add(request, **kw):
            request.headers["Authorization"] = f"Bearer {tok}"
        c.meta.events.register("before-send.bedrock-runtime.*", _add)
    return c


def bedrock(system: str, user: str, max_tokens: int, timeout: float) -> str:
    model = os.environ["BEDROCK_TEXT_MODEL_ID"]
    r = _bedrock().converse(modelId=model, system=[{"text": system}],
                            messages=[{"role": "user", "content": [{"text": user}]}],
                            inferenceConfig={"temperature": 0, "maxTokens": max_tokens})
    return r["output"]["message"]["content"][0]["text"]


def warm() -> None:
    """Open the Bedrock connection at startup: client setup + first TLS call take ≈ 6 s cold,
    which would make the first claim's narrative miss the 4 s swap window. Raises on failure
    (pipeline.warm reports it); a no-op unless Bedrock is the primary and a model is set."""
    if os.environ.get("CLAIMSHIELD_LLM_PRIMARY", "bedrock") == "bedrock" and os.environ.get("BEDROCK_TEXT_MODEL_ID"):
        bedrock("Reply with exactly: OK", "Say OK.", max_tokens=5, timeout=8)


def qwen(system: str, user: str, max_tokens: int, timeout: float) -> str:
    from openai import OpenAI

    c = OpenAI(api_key=os.environ["QWEN_API_KEY"], base_url=os.environ["QWEN_BASE_URL"],
               timeout=timeout)
    r = c.chat.completions.create(model=os.environ["QWEN_MODEL"], temperature=0,
                                  max_tokens=max_tokens,
                                  messages=[{"role": "system", "content": system},
                                            {"role": "user", "content": user}])
    return r.choices[0].message.content


def complete(system: str, user: str, max_tokens: int = 400, timeout: float = 8.0) -> str | None:
    """First provider that answers, primary first; None if all fail or primary=template."""
    primary = os.environ.get("CLAIMSHIELD_LLM_PRIMARY", "bedrock")
    if primary == "template":
        return None
    order = [bedrock, qwen] if primary == "bedrock" else [qwen, bedrock]
    for fn in order:
        try:
            return fn(system, user, max_tokens, timeout)
        except Exception:
            continue
    return None
