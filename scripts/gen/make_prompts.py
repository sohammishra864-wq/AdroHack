"""200 damage-scene prompts (text-to-image + img2img) and short damage phrases (inpaint).

Usage: python scripts/gen/make_prompts.py [--n 200] [--out data/prompts]
Deterministic (fixed RNG), so the HPC and the laptop get the same prompts.
"""
import argparse
import random
from pathlib import Path

SUBJECTS = ["a silver sedan", "a red hatchback", "a white SUV", "a black pickup truck",
            "a blue city car", "a delivery van", "a motorcycle", "a family minivan",
            "the front door of a suburban house", "a brick house exterior", "a garage door",
            "a kitchen ceiling", "a living room wall", "a wooden fence", "a roof with tiles",
            "a laptop on a desk", "a smartphone on a table", "a flat-screen TV",
            "a bathroom floor", "a shop window"]
DAMAGE = {
    "vehicle": ["a deep dent in the rear bumper", "a crushed front bumper and cracked headlight",
                "long scratches along the driver door", "a shattered windscreen",
                "a smashed side mirror", "hail dents across the bonnet",
                "a crumpled rear quarter panel", "a cracked tail light"],
    "property": ["water damage and brown stains", "a large crack in the plaster",
                 "fire and smoke damage", "a broken window pane", "storm damage and missing pieces",
                 "mould patches from a leak", "a hole punched through"],
    "device": ["a cracked screen", "a shattered display with spider-web cracks",
               "water damage and corrosion", "a bent frame and broken corner"],
}
SETTING = ["in a parking lot", "on a residential street", "in a driveway", "at dusk",
           "on an overcast day", "under harsh midday sun", "indoors under warm light",
           "after heavy rain"]
STYLE = ["photo taken with a smartphone", "amateur insurance claim photo",
         "close-up phone photo, slightly tilted", "wide shot, phone camera, natural light",
         "photorealistic, 35mm, candid"]


def kind(subject):
    if any(w in subject for w in ("car", "SUV", "truck", "van", "motorcycle", "sedan", "hatchback")):
        return "vehicle"
    return "device" if any(w in subject for w in ("laptop", "phone", "TV")) else "property"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default="data/prompts")
    a = ap.parse_args()
    rng = random.Random(24)
    prompts = set()
    while len(prompts) < a.n:
        s = rng.choice(SUBJECTS)
        prompts.add(f"{s} with {rng.choice(DAMAGE[kind(s)])}, {rng.choice(SETTING)}, "
                    f"{rng.choice(STYLE)}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "prompts.txt").write_text("\n".join(sorted(prompts)) + "\n", encoding="utf-8")
    inpaint = [f"{d}, photorealistic, matching lighting" for ds in DAMAGE.values() for d in ds]
    (out / "inpaint_prompts.txt").write_text("\n".join(inpaint) + "\n", encoding="utf-8")
    print(f"wrote {len(prompts)} prompts + {len(inpaint)} inpaint prompts to {out}")


if __name__ == "__main__":
    main()
