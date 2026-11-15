"""I5: hierarchical softmax over the generator tree, on CLIP features. Explanation only
(weight 0). P(leaf) = P(branch | root) · P(leaf | branch). Open set: max leaf < 0.60 →
"unknown family". Flux is held out, so on Flux the mass should land on the diffusion node.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from sklearn.linear_model import LogisticRegression

from .. import config
from ..contracts import Signal
from . import clip_probe

NAME = "family_map"
HEAD = "heads/family_map.pkl"
TREE = {"root": ("real", "diffusion", "edited"),
        "diffusion": ("sd15", "sdxl", "flux", "firefly", "midjourney", "nova"),
        "edited": ("splice", "copymove", "inpaint")}
PARENT = {c: p for p, cs in TREE.items() for c in cs}
LEAVES = [c for cs in TREE.values() for c in cs if c not in TREE]
LABEL = {"root": "All", "real": "Real", "diffusion": "Diffusion", "edited": "Edited",
         "sd15": "SD 1.5", "sdxl": "SDXL", "flux": "Flux*", "firefly": "Firefly",
         "midjourney": "Midjourney", "nova": "Nova Canvas", "splice": "Splice",
         "copymove": "Copy-move", "inpaint": "Inpaint"}


class Const:
    """Stand-in classifier when a node saw only one class in training."""
    def __init__(self, c):
        self.classes_ = np.array([c])

    def predict_proba(self, X):
        return np.ones((len(X), 1))


def _clf(X, y):
    classes = np.unique(y)
    if len(classes) == 1:
        return Const(classes[0])
    return LogisticRegression(max_iter=5000, class_weight="balanced").fit(X, y)


def fit(X: np.ndarray, families) -> dict:
    """One classifier per internal node. Rows outside the tree (gan, eval-only) are dropped."""
    fams = np.asarray(families)
    ok = np.isin(fams, LEAVES)
    X, fams = X[ok], fams[ok]
    branch = np.array([f if PARENT[f] == "root" else PARENT[f] for f in fams])
    heads = {"root": _clf(X, branch)}
    for node in ("diffusion", "edited"):
        if (branch == node).any():
            heads[node] = _clf(X[branch == node], fams[branch == node])
    return heads


def node_probs(heads: dict, feat: np.ndarray) -> dict[str, float]:
    def dist(node):
        clf = heads.get(node)
        return dict(zip(clf.classes_, clf.predict_proba(feat[None])[0])) if clf else {}

    p = {"root": 1.0, **{c: 0.0 for c in PARENT}}
    p.update({c: float(v) for c, v in dist("root").items()})
    for node in ("diffusion", "edited"):
        d = dist(node)
        for c in TREE[node]:
            p[c] = p[node] * float(d.get(c, 0.0))
    return p


def sunburst(p: dict[str, float]) -> dict:
    """Plotly sunburst arrays (branchvalues='remainder'; internal nodes carry 0 own value)."""
    ids = ["root", *PARENT]
    return {"ids": ids, "labels": [LABEL[i] for i in ids],
            "parents": ["" if i == "root" else PARENT[i] for i in ids],
            "values": [0.0 if i in TREE else p[i] for i in ids],
            "probs": [p[i] for i in ids]}


def explain(p: dict[str, float]) -> str:
    leaf = max(LEAVES, key=p.get)
    if p[leaf] < config.cfg("thresholds")["family_map"]["unknown_below_maxprob"]:
        b = max(TREE["root"], key=p.get)
        return f"Unknown family; most probability on the {LABEL[b].lower()} branch ({p[b]:.2f})."
    if leaf == "real":
        return f"Looks like a real photo ({p[leaf]:.2f})."
    return f"{LABEL[PARENT[leaf]]} branch, nearest {LABEL[leaf]} ({p[leaf]:.2f})."


@lru_cache(maxsize=1)
def heads():
    return clip_probe.load_head(HEAD)


def warm():
    heads()


def run(prep) -> Signal:
    p = node_probs(heads(), clip_probe.features(prep))
    return Signal(NAME, 1 - p["real"], max(p[c] for c in LEAVES), explain(p),
                  {"probs": p, "sunburst": sunburst(p)})
