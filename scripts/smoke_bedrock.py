"""Bedrock smoke test through the app's own code path (claimshield/llm), credentials from .env.

  1. which settings are present (the token is never printed)
  2. Claude text: llm.bedrock(), the call the narrative uses; errors are shown, not swallowed
  3. the narrative swap: does a rewrite land inside the 4 s window and keep every number?
  4. optional Nova Canvas inpaint on a photo (the arena's first attack step)

If BEDROCK_TEXT_MODEL_ID is unset, it lists the Claude models / inference profiles the account
can see so you can copy one into .env.
Run:  python scripts/smoke_bedrock.py [path/to/photo.jpg]
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from claimshield import llm  # noqa: E402  (importing claimshield loads .env)
from claimshield.narrative import llm as narrative  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
TEXT_MODEL = os.environ.get("BEDROCK_TEXT_MODEL_ID")
IMG_MODEL = os.environ.get("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-canvas-v1:0")


def why(e: Exception) -> str:
    code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
    hint = {"UnrecognizedClientException": "token invalid or expired",
            "AccessDeniedException": "token valid, but this model is not enabled for the account/region "
                                     "(Bedrock console → Model access)",
            "ValidationException": "wrong model ID for this region; on-demand Claude usually needs an "
                                   "inference-profile ID such as us.anthropic.…",
            "ResourceNotFoundException": "model ID not found in this region",
            "ThrottlingException": "rate limited; try again in a minute"}.get(code, "")
    if "api key" in str(e).lower() or "bearer" in str(e).lower():
        hint = "the token itself is wrong: re-copy the full Bedrock API key into .env (no quotes, no spaces)"
    return f"{type(e).__name__} {code}: {e}" + (f"\n      → {hint}" if hint else "")


def settings() -> bool:
    tok = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
    print(f"region            {REGION}")
    print(f"bearer token      {'set (' + str(len(tok)) + ' chars)' if tok else 'MISSING'}")
    print(f"text model        {TEXT_MODEL or 'MISSING'}")
    print(f"LLM primary       {os.environ.get('CLAIMSHIELD_LLM_PRIMARY', 'bedrock')}")
    return bool(tok)


def list_claude() -> None:
    import boto3
    c = boto3.client("bedrock", region_name=REGION)  # control plane, same bearer-token wiring as llm.py
    tok = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if tok:
        c.meta.events.register("before-send.bedrock.*",
                               lambda request, **kw: request.headers.__setitem__("Authorization", f"Bearer {tok}"))
    try:
        profiles = c.list_inference_profiles()["inferenceProfileSummaries"]
        ids = sorted(p["inferenceProfileId"] for p in profiles if "anthropic" in p["inferenceProfileId"])
        print("Claude inference profiles this account can use (copy one into BEDROCK_TEXT_MODEL_ID):")
        print("  " + "\n  ".join(ids) if ids else "  none listed")
    except Exception as e:
        print(f"could not list models: {why(e)}\n  Pick the ID in the Bedrock console → Model catalog.")


def text() -> bool:
    t0 = time.perf_counter()
    try:
        out = llm.bedrock("Reply with exactly: OK", "Say OK.", max_tokens=10, timeout=8)
    except Exception as e:
        print(f"text      FAIL  {why(e)}")
        return False
    print(f"text      PASS  {out.strip()!r} in {time.perf_counter() - t0:.1f} s")
    return True


def narrative_swap() -> None:
    template = ("Overall: HIGH (0.71), high risk — escalate. Main concerns: (1) Shares the same photo "
                "with earlier claim r1_first (2026-10-04). (2) The invoice was saved 2 times. [NAME_1]")
    job = narrative.start(template)
    out = narrative.result(job)
    took = time.perf_counter() - job[1]
    if out:
        print(f"narrative PASS  LLM rewrite landed in {took:.1f} s and kept every number:\n          {out}")
    else:
        print(f"narrative ----  no swap after {took:.1f} s: too slow (> 4 s) or changed a number; "
              "the template text is shown instead (that is the designed fallback)")


def inpaint(path: str) -> None:
    body = {"taskType": "INPAINTING",
            "inPaintingParams": {"image": base64.b64encode(open(path, "rb").read()).decode(),
                                 "maskPrompt": "the largest flat surface",
                                 "text": "large dent and deep scratches in the paint, photorealistic"},
            "imageGenerationConfig": {"numberOfImages": 1, "quality": "standard", "cfgScale": 7.0, "seed": 42}}
    try:
        r = llm._bedrock(read_timeout=60).invoke_model(modelId=IMG_MODEL, body=json.dumps(body),
                                                        contentType="application/json", accept="application/json")
        b = base64.b64decode(json.loads(r["body"].read())["images"][0])
    except Exception as e:
        print(f"inpaint   FAIL  {why(e)}")
        return
    Path("smoke_inpaint.png").write_bytes(b)
    print(f"inpaint   PASS  wrote smoke_inpaint.png ({len(b)} bytes)")


if __name__ == "__main__":
    if not settings():
        sys.exit("\nPut AWS_BEARER_TOKEN_BEDROCK=… in .env (repo root) and run again.")
    if not TEXT_MODEL:
        list_claude()
        sys.exit("\nSet BEDROCK_TEXT_MODEL_ID in .env and run again.")
    if text():
        narrative_swap()
    if len(sys.argv) > 1:
        inpaint(sys.argv[1])
