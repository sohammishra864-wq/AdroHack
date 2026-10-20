"""Download every model the demo needs, then check the system tools. Run on the DEMO laptop
(never on the code-only laptop) while online, from the repo root, inside the venv:

    python scripts/setup/download_models.py              # everything for a CPU demo
    python scripts/setup/download_models.py --gpu        # + SDXL / Flux VAEs (GPU machines)
    python scripts/setup/download_models.py --only clip,vae --skip-arena

Each model is fetched by calling the SAME loader the app uses, so files land exactly where
the code looks (CLAIMSHIELD_MODELS_DIR, default ./models). A second run is instant.
Afterwards set HF_HUB_OFFLINE=1 so nothing tries the network during the demo.
Exit code 1 if anything failed; the table says what and why.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from claimshield import config  # noqa: E402

TRUFOR_GIT = "https://github.com/grip-unina/TruFor"
TRUFOR_WEIGHTS = "https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip"


def clip():
    from claimshield.signals import clip_probe
    clip_probe.model()


def vae_sd15():
    from claimshield.signals import vae
    vae.load("sd15")


def vae_gpu():
    from claimshield.signals import vae
    vae.load("sdxl"), vae.load("flux")


def lpips():
    from claimshield.signals import ae_reconstruction
    ae_reconstruction.lpips_vgg()


def insightface():
    from claimshield.signals.identity import face_match
    face_match.model()


def trufor():
    """Research licence (prototype only). Code is cloned, weights unzipped."""
    root = config.models_dir() / "trufor"
    if not (root / "TruFor_train_test").exists():
        subprocess.run(["git", "clone", "--depth", "1", TRUFOR_GIT, str(root)], check=True)
    w = root / config.cfg("runtime")["trufor"]["weights"].split("/", 1)[1]
    if not w.exists():
        z = root / "TruFor_weights.zip"
        urllib.request.urlretrieve(TRUFOR_WEIGHTS, z)
        with zipfile.ZipFile(z) as zf:
            member = next(n for n in zf.namelist() if n.endswith("trufor.pth.tar"))
            w.write_bytes(zf.read(member))
        z.unlink()
    from claimshield.signals.localizer.trufor import TruFor
    TruFor().warm()  # also proves the runtime.yaml trufor paths match the clone


def arena_sd15():
    from claimshield.arena import attacks
    attacks.warm_local()


STEPS = {  # name: (what, rough size, fn)
    "clip": ("CLIP ViT-L/14 (open_clip, openai)", "1.7 GB", clip),
    "vae": ("SD1.5 VAE (AE reconstruction + fallback localizer)", "0.3 GB", vae_sd15),
    "lpips": ("LPIPS VGG16 (AE reconstruction)", "0.6 GB", lpips),
    "insightface": ("InsightFace buffalo_l (face match)", "0.3 GB", insightface),
    "trufor": ("TruFor code + weights (localizer)", "0.3 GB", trufor),
    "arena": ("SD1.5 inpainting (arena fallback when Bedrock is down)", "4 GB", arena_sd15),
    "vae_gpu": ("SDXL + Flux VAEs (only used with device=cuda)", "0.5 GB", vae_gpu),
}


def tools() -> list[tuple[str, bool, str]]:
    """System tools and settings the app needs besides Python packages."""
    out = []
    try:
        import pytesseract
        out.append(("Tesseract", True, str(pytesseract.get_tesseract_version())))
    except Exception as e:
        out.append(("Tesseract", False, f"{e} — install it and add C:\\Program Files\\Tesseract-OCR to PATH"))
    p = shutil.which("pdftoppm")
    out.append(("Poppler (pdftoppm)", bool(p), p or "not on PATH — add Poppler's Library\\bin folder"))
    p = shutil.which("make")
    out.append(("make", bool(p), p or "not on PATH — or run the Makefile commands by hand"))
    try:
        import c2pa  # noqa: F401
        out.append(("c2pa-python", True, "import ok"))
    except Exception as e:
        out.append(("c2pa-python", False, str(e)))
    heads = [h for h in ("heads/clip_probe.pkl", "heads/family_map.pkl") if not (config.models_dir() / h).exists()]
    out.append(("trained heads", not heads, "present" if not heads else
                f"missing {', '.join(heads)} — run scripts/train_heads.py after the dataset exists"))
    miss = [v for v in ("AWS_BEARER_TOKEN_BEDROCK", "BEDROCK_TEXT_MODEL_ID") if not os.environ.get(v)]
    out.append(("Bedrock env", not miss, "set" if not miss else f"unset: {', '.join(miss)} (narrative "
                "falls back to template, arena to local inpaint)"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma list of: " + ", ".join(STEPS))
    ap.add_argument("--gpu", action="store_true", help="also fetch the SDXL + Flux VAEs")
    ap.add_argument("--skip-arena", action="store_true", help="skip the 4 GB SD1.5 inpainting model")
    a = ap.parse_args()
    names = a.only.split(",") if a.only else [n for n in STEPS if n != "vae_gpu" or a.gpu]
    if a.skip_arena and "arena" in names:
        names.remove("arena")
    print(f"models dir: {config.models_dir()}  (free disk: "
          f"{shutil.disk_usage(ROOT).free / 1e9:.0f} GB)\n")

    rows = []
    for n in names:
        what, size, fn = STEPS[n]
        print(f"→ {what} (~{size}) …", flush=True)
        t0 = time.perf_counter()
        try:
            fn()
            rows.append((what, True, f"ok in {time.perf_counter() - t0:.0f} s"))
        except Exception as e:
            rows.append((what, False, f"{type(e).__name__}: {e}"))
    rows += tools()

    print("\n" + "\n".join(f"  {'OK  ' if ok else 'FAIL'}  {name:<55} {msg}" for name, ok, msg in rows))
    bad = [r for r in rows if not r[1]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} ok." + (" Fix the FAIL lines, then re-run." if bad else
          " Now set HF_HUB_OFFLINE=1 for the demo."))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
