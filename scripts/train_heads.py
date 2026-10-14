"""Train the CLIP probe and the family-map heads on split=train, heldout=0 manifest rows.

Prints held-out (Flux) AUC against test reals. Pre-committed rule: < 0.80 → add a DINOv2
head (ARCHITECTURE.md I2).
Usage: python scripts/train_heads.py [--manifest data/generated/manifest.csv]
"""
import argparse
import csv
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from claimshield import config  # noqa: E402
from claimshield.preprocess import prepare  # noqa: E402
from claimshield.signals import clip_probe, family_map  # noqa: E402


def feats(rows):
    out = []
    for i, r in enumerate(rows):
        out.append(clip_probe.features(prepare(str(ROOT / r["path"]))))
        if i % 200 == 0:
            print(f"  features {i}/{len(rows)}", flush=True)
    return np.stack(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/generated/manifest.csv")
    rows = list(csv.DictReader(open(ROOT / ap.parse_args().manifest, encoding="utf-8")))

    train = [r for r in rows if r["split"] == "train" and r["heldout"] == "0"]
    X = feats(train)
    y = np.array([r["label"] == "fake" for r in train])
    probe = LogisticRegression(max_iter=5000, class_weight="balanced").fit(X, y)
    fam = family_map.fit(X, [r["family"] for r in train])

    out = config.models_dir() / "heads"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clip_probe.pkl").write_bytes(pickle.dumps(probe))
    (out / "family_map.pkl").write_bytes(pickle.dumps(fam))
    print(f"saved heads to {out} (n_train={len(train)})")

    held = [r for r in rows if r["heldout"] == "1"]
    real = [r for r in rows if r["split"] == "test" and r["label"] == "real"]
    if held and real:
        Xe = feats(held + real)
        auc = roc_auc_score([1] * len(held) + [0] * len(real), probe.predict_proba(Xe)[:, 1])
        print(f"held-out Flux AUC = {auc:.3f}" + ("  → below 0.80: add DINOv2 head" if auc < 0.8 else ""))


if __name__ == "__main__":
    main()
