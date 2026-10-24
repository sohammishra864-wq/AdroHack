"""Loads configs/*.yaml once. Everything tunable lives there, not in code."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path = ROOT / ".env") -> None:
    """KEY=VALUE lines from .env into os.environ. A variable already set in the shell wins,
    and empty values are skipped, so `.env` never blanks out a real setting."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        k, sep, v = line.strip().partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if sep and k and v and not k.startswith("#"):
            os.environ.setdefault(k, v)


load_env()


@lru_cache(maxsize=None)
def cfg(name: str) -> dict:
    return yaml.safe_load((ROOT / "configs" / f"{name}.yaml").read_text(encoding="utf-8"))


def models_dir() -> Path:
    return Path(os.environ.get("CLAIMSHIELD_MODELS_DIR") or ROOT / "models")


def hf_cache() -> str:
    """Hugging Face hub cache: HF_HUB_CACHE when the machine sets one (HPC: models/hf/hub),
    else <models>/hf (what download_models.py fills on the laptop)."""
    return os.environ.get("HF_HUB_CACHE") or str(models_dir() / "hf")


def device() -> str:
    return os.environ.get("CLAIMSHIELD_DEVICE") or cfg("runtime")["device"]
