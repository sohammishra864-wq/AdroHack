import numpy as np
import pytest

from claimshield.signals import family_map as fm

FAMS = ["real", "sd15", "sdxl", "firefly", "splice", "inpaint"]  # flux held out


def data(seed=0, n=40):
    rng = np.random.default_rng(seed)
    centres = {f: rng.normal(0, 3, 16) for f in FAMS}
    X = np.concatenate([centres[f] + rng.normal(0, 0.5, (n, 16)) for f in FAMS])
    return X, [f for f in FAMS for _ in range(n)], centres


def test_probabilities_are_a_proper_hierarchy():
    X, y, c = data()
    p = fm.node_probs(fm.fit(X, y), c["sdxl"])
    assert p["root"] == 1.0
    assert sum(p[b] for b in fm.TREE["root"]) == pytest.approx(1.0)
    for node in ("diffusion", "edited"):
        assert sum(p[c] for c in fm.TREE[node]) == pytest.approx(p[node])
    assert p["flux"] == 0.0 and max(fm.LEAVES, key=p.get) == "sdxl"


def test_eval_only_gan_rows_never_train():
    X, y, _ = data()
    heads = fm.fit(np.vstack([X, X[:5]]), y + ["gan"] * 5)
    assert "gan" not in heads["root"].classes_


def test_open_set_rule_says_unknown():
    p = {k: 0.0 for k in ["root", *fm.PARENT]}
    p.update(root=1.0, diffusion=0.9, real=0.1, sd15=0.45, sdxl=0.45)
    assert fm.explain(p).startswith("Unknown family") and "diffusion" in fm.explain(p)


def test_sunburst_shape():
    X, y, c = data()
    sb = fm.sunburst(fm.node_probs(fm.fit(X, y), c["real"]))
    assert len(sb["ids"]) == len(sb["parents"]) == len(sb["values"]) == 13
    assert sb["parents"][0] == ""
