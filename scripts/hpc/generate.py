"""HPC job: SD1.5 / SDXL / Flux × {t2i, img2img, inpaint} → data/generated/<family>/<attack>/.

Runs on a GPU compute node with no internet: weights must already be in $HF_HOME (download
on the login node, see scripts/hpc/README.md). Resumable: existing outputs are skipped, and
each <family>/<attack>/_rows.csv is rewritten after every batch, so a job that hits its time
limit can simply be resubmitted. Flux is the held-out family; scripts/gen/manifest.py tags it.

Usage (from the repo root / $SCRATCH/claimshield):
  python scripts/hpc/generate.py --models sd15,sdxl,flux --n 134
"""
import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from rows import images, open_rgb, write  # noqa: E402

# id, inpaint id (None → reuse the base weights), variant, px, steps, guidance
MODELS = {
    "sd15": ("stable-diffusion-v1-5/stable-diffusion-v1-5",
             "stable-diffusion-v1-5/stable-diffusion-inpainting", "fp16", 512, 30, 7.5),
    "sdxl": ("stabilityai/stable-diffusion-xl-base-1.0",
             "diffusers/stable-diffusion-xl-1.0-inpainting-0.1", "fp16", 1024, 30, 7.0),
    "flux": ("black-forest-labs/FLUX.1-schnell", None, None, 1024, 4, 0.0),
}
IMG2IMG_STRENGTH, INPAINT_STRENGTH = 0.6, 0.95
NEG = "cartoon, illustration, painting, text, watermark"


def fit(img, px):
    """Long side = px, both sides a multiple of 16."""
    s = px / max(img.size)
    return img.resize(tuple(max(16, round(d * s / 16) * 16) for d in img.size))


def load(name, attack):
    import torch
    from diffusers import (AutoPipelineForImage2Image, AutoPipelineForInpainting,
                           AutoPipelineForText2Image)

    mid, inpaint_id, variant, *_ = MODELS[name]
    kw = {"torch_dtype": torch.bfloat16 if name == "flux" else torch.float16}
    if variant:
        kw["variant"] = variant
    if name == "sd15":
        # NSFW checker false-fires on damage photos → all-black output; seeds are fixed, so a
        # rerun would black out the same image again
        kw["safety_checker"] = None
    if attack == "inpaint" and inpaint_id:
        return AutoPipelineForInpainting.from_pretrained(inpaint_id, **kw).to("cuda")
    pipe = AutoPipelineForText2Image.from_pretrained(mid, **kw).to("cuda")
    if attack == "img2img":
        return AutoPipelineForImage2Image.from_pipe(pipe)
    return AutoPipelineForInpainting.from_pipe(pipe) if attack == "inpaint" else pipe


def run(pipe, name, attack, prompt, seed_img, mask, gen):
    _, _, _, px, steps, cfg = MODELS[name]
    kw = {"prompt": prompt, "guidance_scale": cfg, "generator": gen}
    if name != "flux":
        kw["negative_prompt"] = NEG
    if attack == "t2i":
        return pipe(height=px, width=px, num_inference_steps=steps, **kw).images[0]
    img = fit(seed_img, px)
    strength = IMG2IMG_STRENGTH if attack == "img2img" else INPAINT_STRENGTH
    # keep the number of denoising steps actually run ≈ `steps` whatever the strength
    kw.update(image=img, strength=strength, num_inference_steps=math.ceil(steps / strength),
              height=img.height, width=img.width)
    if attack == "img2img":
        return pipe(**kw).images[0]
    from PIL import Image, ImageFilter
    m = mask.resize(img.size)
    out = pipe(mask_image=m, **kw).images[0].resize(img.size)
    # paste back only the masked area, as a fraudster would; outside stays camera pixels
    return Image.composite(out, img, m.filter(ImageFilter.GaussianBlur(4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="sd15,sdxl,flux")
    ap.add_argument("--attacks", default="t2i,img2img,inpaint")
    ap.add_argument("--n", type=int, default=134, help="images per model per attack")
    ap.add_argument("--seeds", default="data/seeds")
    ap.add_argument("--masks", default="data/masks")
    ap.add_argument("--prompts", default="data/prompts")
    ap.add_argument("--out", default="data/generated")
    a = ap.parse_args()

    import torch

    prompts = Path(a.prompts, "prompts.txt").read_text(encoding="utf-8").split("\n")
    inpaint_prompts = Path(a.prompts, "inpaint_prompts.txt").read_text(encoding="utf-8").split("\n")
    prompts, inpaint_prompts = [p for p in prompts if p], [p for p in inpaint_prompts if p]
    seeds = [p for p in images(a.seeds) if "whatsapp" not in p.parts]
    if not seeds and a.attacks != "t2i":
        sys.exit(f"no seed images in {a.seeds}")

    for name in a.models.split(","):
        for attack in a.attacks.split(","):
            out_dir = Path(a.out, name, attack)
            out_dir.mkdir(parents=True, exist_ok=True)
            pipe, rows = None, []
            for i in range(a.n):
                rng = random.Random(f"{name}/{attack}/{i}")
                seed = seeds[i % len(seeds)] if attack != "t2i" else None
                mask = Path(a.masks, f"{seed.stem}.png") if attack == "inpaint" else None
                prompt = rng.choice(inpaint_prompts if attack == "inpaint" else prompts)
                path = out_dir / f"{i:04d}.jpg"
                rows.append({"path": path, "label": "fake", "family": name, "attack": attack,
                             "quality": "orig", "seed_path": seed or "", "mask_path": mask or ""})
                if path.exists():
                    continue
                if pipe is None:
                    pipe = load(name, attack)
                from PIL import Image
                img = run(pipe, name, attack, prompt, open_rgb(seed) if seed else None,
                          Image.open(mask).convert("L") if mask else None,
                          torch.Generator("cuda").manual_seed(rng.randrange(2**31)))
                img.save(path, quality=95)
                if i % 20 == 0:
                    write(out_dir, rows)
                    print(f"{name}/{attack}: {i + 1}/{a.n}", flush=True)
            write(out_dir, rows)
            del pipe
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
