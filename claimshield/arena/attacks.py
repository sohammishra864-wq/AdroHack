"""Red-team arena attacks (ARCHITECTURE § Arena).

inpaint:        Nova Canvas INPAINTING (maskPrompt) → local SD1.5 inpaint on CPU →
                a pre-generated attack, shown with one honest sentence.
recompress_q70: JPEG re-encode at quality 70 (local, always works).
Every attack returns JPEG bytes; the caller writes them to a temp file and re-scores.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .. import config


@dataclass
class Attack:
    data: bytes     # JPEG bytes of the attacked image
    kind: str       # inpaint | recompress_q70
    method: str     # nova | local_sd15 | pregenerated | recompress
    note: str       # one honest sentence for the screen
    seconds: float


def _cfg() -> dict:
    return config.cfg("runtime")["arena"]


def _open(path) -> Image.Image:
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def _jpeg(img: Image.Image, q: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return buf.getvalue()


def _fit(img: Image.Image, px: int, mult: int) -> Image.Image:
    s = px / max(img.size)
    return img.resize(tuple(max(mult, round(d * s / mult) * mult) for d in img.size))


def damage_mask(size) -> Image.Image:
    """White ellipse in the lower-middle third (~10 % of the frame): where bumpers, doors
    and floors usually are. The local path has no maskPrompt."""
    W, H = size
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse((0.32 * W, 0.52 * H, 0.68 * W, 0.86 * H), fill=255)
    return m


def inpaint_nova(img: Image.Image, prompt: str, mask_prompt: str) -> Image.Image:
    from ..llm import _bedrock

    small = _fit(img, 1024, 16)  # Nova: sides multiple of 16, ≤ 4.19 MP
    buf = io.BytesIO()
    small.save(buf, "PNG")
    body = {"taskType": "INPAINTING",
            "inPaintingParams": {"image": base64.b64encode(buf.getvalue()).decode(),
                                 "maskPrompt": mask_prompt, "text": prompt},
            "imageGenerationConfig": {"numberOfImages": 1, "quality": "standard",
                                      "cfgScale": 7.0, "seed": 42}}
    r = _bedrock(_cfg()["nova_timeout_s"]).invoke_model(
        modelId=os.environ.get("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-canvas-v1:0"),
        body=json.dumps(body), contentType="application/json", accept="application/json")
    out = json.loads(r["body"].read())["images"][0]
    return Image.open(io.BytesIO(base64.b64decode(out))).convert("RGB")


@lru_cache(maxsize=1)
def _sd15():
    from diffusers import AutoPipelineForInpainting

    return AutoPipelineForInpainting.from_pretrained(
        _cfg()["local_model"], cache_dir=config.hf_cache()).to(config.device())


def warm_local():
    _sd15()


def inpaint_local_sd15(img: Image.Image, prompt: str) -> Image.Image:
    """SD1.5 inpaint at local_px on CPU; only the masked area is pasted back at full size."""
    A = _cfg()
    small = _fit(img, A["local_px"], 8)
    mask = damage_mask(small.size)
    out = _sd15()(prompt=prompt, image=small, mask_image=mask, height=small.height,
                  width=small.width, num_inference_steps=A["local_steps"]).images[0]
    # ponytail: patch is generated at 384 px and upscaled → softer than the photo around it.
    soft = damage_mask(img.size).filter(ImageFilter.GaussianBlur(max(2, img.width // 200)))
    return Image.composite(out.resize(img.size), img, soft)


def pregenerated(kind: str) -> Path | None:
    d = config.ROOT / _cfg()["pregenerated_dir"]
    files = sorted(d.glob(f"{kind}_*.jpg")) if d.exists() else []
    return files[0] if files else None


def inpaint(path, prompt: str | None = None) -> Attack:
    """Nova → local SD1.5 → pre-generated. Raises only if all three are unavailable."""
    A, img, errors = _cfg(), _open(path), []
    prompt = prompt or A["prompt"]
    chain = (("nova", lambda: inpaint_nova(img, prompt, A["mask_prompt"]),
              "Live attack: Amazon Nova Canvas painted the damage onto this photo."),
             ("local_sd15", lambda: inpaint_local_sd15(img, prompt),
              "Bedrock unavailable, so Stable Diffusion 1.5 painted the damage locally on CPU."))
    for method, fn, note in chain:
        t0 = time.perf_counter()
        try:
            return Attack(_jpeg(fn(), 95), "inpaint", method, note, time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"{method}: {type(e).__name__}: {e}")
    p = pregenerated("inpaint")
    if p is None:
        raise RuntimeError("no attack path available — " + "; ".join(errors))
    return Attack(p.read_bytes(), "inpaint", "pregenerated", "Live attack unavailable, so this "
                  "is an attack generated before the demo on a different photo.", 0.0)


def recompress_q70(path) -> Attack:
    t0 = time.perf_counter()
    return Attack(_jpeg(_open(path), 70), "recompress_q70", "recompress",
                  "Re-saved as a JPEG at quality 70, as messaging apps do.", time.perf_counter() - t0)


ATTACKS = {"inpaint": inpaint, "recompress_q70": recompress_q70}
