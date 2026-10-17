"""Nova Canvas (Bedrock) inpaint + variation on N seeds → data/generated/nova/<attack>/.

Needs AWS_BEARER_TOKEN_BEDROCK (see .env.example) and data/masks from masks.py. Costs about
2 × N Nova standard images. Resumable: existing outputs are skipped.
Usage: python scripts/gen/nova_attacks.py [--n 150]
"""
import argparse
import base64
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageOps

from rows import images, open_rgb, write

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_bedrock import IMG_MODEL, client  # noqa: E402


def b64(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def fit(img):
    """Nova wants each side 320–4096 and a multiple of 16; long side 1024."""
    s = 1024 / max(img.size)
    return img.resize(tuple(max(320, round(d * s / 16) * 16) for d in img.size))


def call(c, body):
    r = c.invoke_model(modelId=IMG_MODEL, body=json.dumps(body),
                       contentType="application/json", accept="application/json")
    return Image.open(io.BytesIO(base64.b64decode(json.loads(r["body"].read())["images"][0])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seeds", default="data/seeds")
    ap.add_argument("--masks", default="data/masks")
    ap.add_argument("--prompts", default="data/prompts")
    a = ap.parse_args()
    c = client()
    seeds = [p for p in images(a.seeds) if "whatsapp" not in p.parts][:a.n]
    inpaint_prompts = [p for p in Path(a.prompts, "inpaint_prompts.txt")
                       .read_text(encoding="utf-8").split("\n") if p]
    rows = {"inpaint": [], "variation": []}
    for i, seed in enumerate(seeds):
        rng = random.Random(f"nova/{seed.name}")
        img = fit(open_rgb(seed))
        mask_path = Path(a.masks, f"{seed.stem}.png")
        cfg = {"numberOfImages": 1, "quality": "standard", "cfgScale": 7.0,
               "seed": rng.randrange(2**31)}
        for attack in rows:
            out = Path("data/generated/nova", attack, f"{i:04d}.jpg")
            out.parent.mkdir(parents=True, exist_ok=True)
            rows[attack].append({"path": out, "label": "fake", "family": "nova", "attack": attack,
                                 "quality": "orig", "seed_path": seed,
                                 "mask_path": mask_path if attack == "inpaint" else ""})
            if out.exists():
                continue
            if attack == "inpaint":
                # Nova: black = area to edit (our masks are white = edit), same size as image
                mask = ImageOps.invert(Image.open(mask_path).convert("L").resize(img.size))
                body = {"taskType": "INPAINTING",
                        "inPaintingParams": {"image": b64(img), "maskImage": b64(mask.convert("RGB")),
                                             "text": rng.choice(inpaint_prompts)}}
            else:
                body = {"taskType": "IMAGE_VARIATION",
                        "imageVariationParams": {"images": [b64(img)], "similarityStrength": 0.8,
                                                 "text": "same scene, photorealistic phone photo"}}
            try:
                call(c, {**body, "imageGenerationConfig": cfg}).convert("RGB").save(out, quality=95)
            except Exception as e:  # content filter / throttling: skip the seed, keep going
                rows[attack].pop()
                print(f"{seed.name} {attack}: {type(e).__name__}: {e}", flush=True)
        if i % 10 == 0:
            print(f"nova: {i + 1}/{len(seeds)}", flush=True)
    for attack, rs in rows.items():
        write(Path("data/generated/nova", attack), rs)


if __name__ == "__main__":
    main()
