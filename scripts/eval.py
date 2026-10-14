"""Eval harness (README): the 9 published rows → reports/eval_latest.md.

  python scripts/eval.py --dry                  # validate manifests only (Gate 2)
  python scripts/eval.py                        # full run (make eval)
  python scripts/eval.py --calibrate            # fit sigmoids on calib first, then report
  python scripts/eval.py --subset 500 --signals clip_probe,localizer,c2pa

Train rows are never scored; calib rows only with --calibrate and never reported.
Per-image results are cached in data/cache/eval/, so a re-run after a weight change is fast.
"""
import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLS = ["path", "label", "family", "attack", "quality", "heldout", "split", "seed_path", "mask_path"]
ENUMS = {
    "label": {"real", "fake"},
    "family": {"real", "sd15", "sdxl", "flux", "firefly", "midjourney", "nova", "splice",
               "copymove", "inpaint", "gan"},
    "quality": {"orig", "q90", "q70", "q50", "dn512", "whatsapp"},
    "heldout": {"0", "1"},
    "split": {"train", "calib", "test", "eval_only", "wild"},
}
NEEDS_MASK = {"inpaint", "splice", "copymove"}


def check_images(rows):
    errs = []
    if not rows or list(rows[0]) != COLS:
        return [f"columns must be exactly {COLS}"]
    for i, r in enumerate(rows, 2):
        errs += [f"line {i}: {k}={r[k]!r} not in {sorted(v)}" for k, v in ENUMS.items()
                 if r[k] not in v]
        for k in ("path", "seed_path", "mask_path"):
            if r[k] and not (ROOT / r[k]).exists():
                errs.append(f"line {i}: {k} missing on disk: {r[k]}")
        if (r["label"] == "real") != (r["family"] == "real"):
            errs.append(f"line {i}: label/family disagree")
        if (r["family"] == "flux") != (r["heldout"] == "1"):
            errs.append(f"line {i}: flux ⇔ heldout=1 violated")
        if r["heldout"] == "1" and r["split"] in ("train", "calib"):
            errs.append(f"line {i}: held-out row in {r['split']}")
        if (r["family"] == "gan") != (r["split"] == "eval_only"):
            errs.append(f"line {i}: gan ⇔ eval_only violated")
        if r["attack"] in NEEDS_MASK and not r["mask_path"]:
            errs.append(f"line {i}: {r['attack']} row without mask_path")
    # a seed may feed only one of train / calib / test (held-out rows are exempt)
    splits = defaultdict(set)
    for r in rows:
        if r["seed_path"] and r["heldout"] == "0" and r["split"] in ("train", "calib", "test"):
            splits[r["seed_path"]].add(r["split"])
    errs += [f"seed {s} leaks across {sorted(v)}" for s, v in splits.items() if len(v) > 1]
    if len({r["path"] for r in rows}) != len(rows):
        errs.append("duplicate paths")
    for need in ("train", "calib", "test"):
        if not any(r["split"] == need and r["heldout"] == "0" for r in rows):
            errs.append(f"no heldout=0 rows in split={need}")
    if not any(r["heldout"] == "1" for r in rows):
        errs.append("no held-out (flux) rows")
    return errs


def check_docs(rows):
    errs = []
    for i, r in enumerate(rows, 2):
        if not (ROOT / r["path"]).exists():
            errs.append(f"docs line {i}: missing {r['path']}")
        if (r["label"] == "tampered") != (r["tamper"] != "none"):
            errs.append(f"docs line {i}: label/tamper disagree")
    return errs


def dry(manifest):
    rows = list(csv.DictReader(open(ROOT / manifest, encoding="utf-8")))
    errs = check_images(rows)
    print(f"{manifest}: {len(rows)} rows")
    for k in ("split", "family", "quality"):
        print(f"  {k}: {dict(Counter(r[k] for r in rows))}")
    docs = ROOT / "data/docs/manifest.csv"
    if docs.exists():
        drows = list(csv.DictReader(open(docs, encoding="utf-8")))
        errs += check_docs(drows)
        print(f"data/docs/manifest.csv: {len(drows)} rows, "
              f"{dict(Counter(r['tamper'] for r in drows))}")
    else:
        errs.append("data/docs/manifest.csv missing (run scripts/gen/tamper_pdf.py)")
    for e in errs[:50]:
        print("ERROR", e)
    print("DRY OK" if not errs else f"DRY FAILED: {len(errs)} problems")
    return not errs


# ---------------------------------------------------------------- scoring run (Phase 8)
CACHE = ROOT / "data" / "cache" / "eval"
ALL = ["c2pa", "exif", "jpeg_qtables", "copy_move", "noise_residual", "clip_probe",
       "family_map", "localizer", "ae_reconstruction"]
QUALS = ["orig", "q90", "q70", "q50", "dn512", "whatsapp"]


def _checks():
    sys.path.insert(0, str(ROOT))
    from claimshield import pipeline
    from claimshield.signals import ae_reconstruction

    fns = {fn.__module__.rsplit(".", 1)[-1]: fn for g in pipeline.FAST.values() for fn in g}
    fns["ae_reconstruction"] = ae_reconstruction.run
    return fns


def _iou(prep, mask_path, impl):
    import cv2
    import numpy as np
    from PIL import Image

    from claimshield import config
    from claimshield.signals import localizer

    r = localizer.get(impl)(prep.rgb)
    hot = cv2.resize(r.heatmap.astype(np.float32), prep.rgb.size) >= 0.5
    if r.reliability is not None:
        rel = cv2.resize(r.reliability.astype(np.float32), prep.rgb.size)
        hot &= rel >= config.cfg("thresholds")["localizer"]["reliability_min"]
    gt = np.asarray(Image.open(ROOT / mask_path).convert("L").resize(prep.rgb.size)) > 127
    union = (hot | gt).sum()
    return float((hot & gt).sum() / union) if union else None


def score_row(row, names, fns, impls):
    """Per-image cache data/cache/eval/<sha>.json keeps every signal ever computed for that
    image, so a weight or calibration change re-scores without re-running any model."""
    from claimshield.pipeline import _pool, _safe
    from claimshield.preprocess import prepare
    from claimshield.signals.family_map import LEAVES

    prep = prepare(str(ROOT / row["path"]))
    f = CACHE / f"{prep.sha256}.json"
    c = json.loads(f.read_text()) if f.exists() else {"signals": {}, "iou": {}}
    c["quality_flag"] = prep.quality_flag
    todo = [n for n in names if n not in c["signals"]]
    for n, fut in [(n, _pool.submit(_safe, fns[n], prep)) for n in todo]:
        s = fut.result()
        c["signals"][n] = [s.score, s.confidence, s.applicable, s.abstained, s.tier]
        if n == "family_map" and s.score is not None:
            p = s.evidence["probs"]
            c["family"] = {"leaf": max(LEAVES, key=p.get), "diffusion": p["diffusion"],
                           "real": p["real"]}
    if row["mask_path"] and row["attack"] in NEEDS_MASK:
        for impl in impls:
            if impl not in c["iou"]:
                try:
                    c["iou"][impl] = _iou(prep, row["mask_path"], impl)
                except Exception as e:
                    c["iou"][impl] = None
                    print(f"  iou {impl} failed: {type(e).__name__}: {e}")
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(c))
    return c


def composite(c, names):
    from claimshield.contracts import Signal
    from claimshield.scoring.composite import score_claim

    sigs = [Signal(n, v[0], v[1], "", {}, v[3], v[2], v[4])
            for n, v in c["signals"].items() if n in names]
    return score_claim(sigs, quality_flag=c["quality_flag"])


def usable(c, n):
    v = c["signals"].get(n)
    return v is not None and v[0] is not None and v[2] and not v[3]


# ------------------------------------------------------------------------- metrics
def metrics(y, s):
    """(AUC, AP, TPR@1%FPR, TPR@5%FPR); None when a class is missing."""
    from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

    if len(set(y)) < 2:
        return None
    fpr, tpr, _ = roc_curve(y, s)

    def at(t):
        return max(tp for fp, tp in zip(fpr, tpr) if fp <= t)
    return roc_auc_score(y, s), average_precision_score(y, s), at(0.01), at(0.05)


def wilson(k, n, z=1.96):
    """95 % Wilson score interval for k successes in n."""
    if n == 0:
        return float("nan"), float("nan")
    p, d = k / n, 1 + z * z / n
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p + z * z / (2 * n) - m) / d, (p + z * z / (2 * n) + m) / d


def fmt(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def auc_of(pos, neg, key):
    """AUC of key(row) for positive vs negative rows; rows without a value are dropped."""
    pts = [(1, key(r)) for r in pos] + [(0, key(r)) for r in neg]
    pts = [(y, v) for y, v in pts if v is not None]
    m = metrics([y for y, _ in pts], [v for _, v in pts]) if pts else None
    return m[0] if m else None


def rate(rows, hit):
    return sum(map(hit, rows)) / len(rows) if rows else None


# -------------------------------------------------------------------------- report
def report(rows, res, names, docs, a, note):
    from claimshield.signals.family_map import LEAVES

    comp = {r["path"]: composite(res[r["path"]], names) for r in rows}

    def sig(n):
        return lambda r: res[r["path"]]["signals"][n][0] if usable(res[r["path"]], n) else None

    def over(r):
        return comp[r["path"]].overall

    def band_in(*bands):
        return lambda r: comp[r["path"]].band in bands

    def pick(**kw):
        return [r for r in rows if all(r[k] == v for k, v in kw.items())]

    reals = pick(split="test", label="real", heldout="0")
    seen, held = pick(split="test", label="fake", heldout="0"), pick(heldout="1")
    wild, gan = pick(split="wild"), pick(split="eval_only")
    faces = [r for r in wild if "/faces/" in r["path"]]

    L = [f"# ClaimShield eval — {datetime.now():%Y-%m-%d %H:%M}", "",
         f"Manifest `{a.manifest}`; {len(rows)} image rows scored"
         + (f" (random subset {a.subset}, seed 0)" if a.subset else "")
         + f". Signals: {', '.join(names)}. Train and calib rows are never reported.", ""]

    L += ["## 1. Composite — test-seen vs test-heldout (Flux)", "",
          "| set | n fake | n real | AUC | AP | TPR@1%FPR | TPR@5%FPR |",
          "|---|---|---|---|---|---|---|"]
    for label, fakes in (("test-seen", seen), ("test-heldout (Flux)", held)):
        m = metrics([1] * len(fakes) + [0] * len(reals), [over(r) for r in fakes + reals])
        L.append(f"| {label} | {len(fakes)} | {len(reals)} | "
                 + (" | ".join(fmt(x) for x in m) if m else "— | — | — | —") + " |")

    L += ["", "## 2. Real-wild false-positive rate", "",
          "| flagged at | n | FP | FPR | 95 % CI (Wilson) |", "|---|---|---|---|---|"]
    for name, hit in (("HIGH", band_in("HIGH")), ("MEDIUM or HIGH", band_in("MEDIUM", "HIGH"))):
        k = sum(map(hit, wild))
        lo, hi = wilson(k, len(wild))
        L.append(f"| {name} | {len(wild)} | {k} | {fmt(rate(wild, hit))} | {fmt(lo)}–{fmt(hi)} |")
    unc = band_in("UNCERTAIN")
    L += ["", f"Abstain (UNCERTAIN) rate: real-wild {fmt(rate(wild, unc))}, "
          f"q50 {fmt(rate([r for r in rows if r['quality'] == 'q50'], unc))}, "
          f"dn512 {fmt(rate([r for r in rows if r['quality'] == 'dn512'], unc))}. "
          f"Real face crops (data/wild/faces/) at HIGH: {sum(map(band_in('HIGH'), faces))} of "
          f"{len(faces)} — target 0; if not, raise the quality-gate cap on faces, never the weights."]

    L += ["", "## 3. Documents — tamper precision / recall", ""]
    if docs:
        L += ["| flagged at | precision | recall | n docs |", "|---|---|---|---|"]
        for name, bands in (("HIGH", {"HIGH"}), ("MEDIUM or HIGH", {"MEDIUM", "HIGH"})):
            tp = sum(d["band"] in bands and d["label"] == "tampered" for d in docs)
            pp = sum(d["band"] in bands for d in docs)
            pos = sum(d["label"] == "tampered" for d in docs)
            L.append(f"| {name} | {fmt(tp / pp if pp else None)} | "
                     f"{fmt(tp / pos if pos else None)} | {len(docs)} |")
        L += ["", "| tampered group (recall at MEDIUM or HIGH) | recall | n |", "|---|---|---|"]
        tam = [d for d in docs if d["label"] == "tampered"]
        for key in ("tamper", "scan", "doc_type"):
            for g in sorted({d[key] for d in tam}):
                ds = [d for d in tam if d[key] == g]
                L.append(f"| {key}={g} | {fmt(rate(ds, lambda d: d['band'] in ('MEDIUM', 'HIGH')))} | {len(ds)} |")
        clean = [d for d in docs if d["label"] == "clean"]
        L.append(f"\nClean documents flagged at MEDIUM or HIGH: "
                 f"{fmt(rate(clean, lambda d: d['band'] in ('MEDIUM', 'HIGH')))} (n={len(clean)}).")
    else:
        L.append("Not run (no data/docs/manifest.csv, or --no-docs).")

    L += ["", "## 4. Signal × family (AUC against test reals; eval-only GAN row included)", "",
          "| family | n | " + " | ".join(names) + " | composite |",
          "|---|---|" + "---|" * (len(names) + 1)]
    for fam in sorted({r["family"] for r in seen + held + gan}):
        fk = [r for r in seen + held + gan if r["family"] == fam]
        L.append(f"| {fam}{' (eval-only)' if fam == 'gan' else ''}{' (held out)' if fk[0]['heldout'] == '1' else ''}"
                 f" | {len(fk)} | " + " | ".join(fmt(auc_of(fk, reals, sig(n)), 2) for n in names)
                 + f" | {fmt(auc_of(fk, reals, over), 2)} |")

    masked = [r for r in seen + held if r["attack"] in NEEDS_MASK and r["mask_path"]]
    L += ["", "## 5. Localizer IoU vs ground-truth mask (reliability-masked)", "",
          "| impl | mean IoU | n |", "|---|---|---|"]
    for impl in a.impls:
        v = [x for x in (res[r["path"]]["iou"].get(impl) for r in masked) if x is not None]
        L.append(f"| {impl} | {fmt(sum(v) / len(v) if v else None)} | {len(v)} |")

    def fm(r):
        return res[r["path"]].get("family")
    known = [r for r in seen + reals if r["family"] in LEAVES and fm(r)]
    dm = [fm(r)["diffusion"] for r in held if fm(r)]
    fc = [r for r in faces if fm(r)]
    L += ["", "## 6. Family map", "",
          f"- Leaf accuracy on seen families: {fmt(rate(known, lambda r: fm(r)['leaf'] == r['family']))} (n={len(known)})",
          f"- Mean diffusion-node mass on Flux (held out): {fmt(sum(dm) / len(dm) if dm else None)} (n={len(dm)})",
          f"- Real face crops not mapped to Real: {sum(fm(r)['leaf'] != 'real' for r in fc)} of {len(fc)} (target ≈ 0)"]

    L += ["", "## 7. Robustness — AUC by quality (test, heldout=0; reals of the same quality)", "",
          "| signal | " + " | ".join(QUALS) + " |", "|---|" + "---|" * len(QUALS)]
    for n, key in [*[(n, sig(n)) for n in names], ("composite", over)]:
        L.append(f"| {n} | " + " | ".join(
            fmt(auc_of([r for r in seen if r["quality"] == q], [r for r in reals if r["quality"] == q], key), 2)
            for q in QUALS) + " |")

    L += ["", "## 8. Arena — attack × signal (reports/arena.csv)", "", arena_table()]
    lat = ROOT / "reports" / "latency_latest.md"
    L += ["", "## 9. Latency", "", lat.read_text(encoding="utf-8").strip() if lat.exists()
          else "Not run yet (`reports/latency_latest.md` missing)."]

    B = cfg_bands()
    table = {"families": {}, "robustness": {}}
    for fam in ("sd15", "sdxl", "nova", "flux", "gan"):
        fk = [r for r in seen + held + gan if r["family"] == fam]
        m = metrics([1] * len(fk) + [0] * len(reals), [over(r) for r in fk + reals]) if fk else None
        table["families"][fam] = {"n": len(fk), "heldout": fam == "flux", "eval_only": fam == "gan",
                                  "auc": m and m[0], "tpr_at_1fpr": m and m[2],
                                  "flagged_high": rate(fk, lambda r: over(r) >= B["medium_max"])}
    for q in QUALS:
        table["robustness"][q] = auc_of([r for r in seen if r["quality"] == q],
                                        [r for r in reals if r["quality"] == q], over)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "heldout_table.json").write_text(json.dumps(table, indent=1), encoding="utf-8")

    cal = (ROOT / "configs" / "calibration.yaml").exists()
    L += ["", "## Changelog", "", note or ("configs/calibration.yaml applied (fitted earlier)." if cal
                                            else "No calibration file: raw signal scores.")]
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out}")


def cfg_bands():
    from claimshield import config
    return config.cfg("thresholds")["bands"]


def arena_table():
    """Per method: n, mean overall before → after, share flagged MEDIUM/HIGH after, and the
    mean after-score of each signal."""
    p = ROOT / "reports" / "arena.csv"
    if not p.exists():
        return "Not run yet (`python -m claimshield.arena.run`)."
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    sigs = sorted({k[6:] for r in rows for k in r if k.startswith("after_")})
    L = ["| method | n | overall before → after | flagged after | " + " | ".join(sigs) + " |",
         "|---|---|---|---|" + "---|" * len(sigs)]
    for m in sorted({r["method"] for r in rows}):
        rs = [r for r in rows if r["method"] == m]

        def mean(k):
            v = [float(r[k]) for r in rs if r.get(k) not in (None, "")]
            return sum(v) / len(v) if v else None
        L.append(f"| {m} | {len(rs)} | {fmt(mean('overall_before'), 2)} → {fmt(mean('overall_after'), 2)} | "
                 f"{fmt(rate(rs, lambda r: r['band_after'] in ('MEDIUM', 'HIGH')), 2)} | "
                 + " | ".join(fmt(mean('after_' + n), 2) for n in sigs) + " |")
    return "\n".join(L)


def calibrate(rows, res, names):
    """Platt sigmoid per signal on calib rows (quality=orig) → configs/calibration.yaml.
    Suggested image-lane weights go into the changelog only: weights.yaml is a human edit."""
    import numpy as np
    import yaml
    from sklearn.linear_model import LogisticRegression

    from claimshield import config

    calib = [r for r in rows if r["split"] == "calib" and r["quality"] == "orig"]
    cal = {}
    for n in names:
        pts = [(res[r["path"]]["signals"][n][0], r["label"] == "fake") for r in calib
               if usable(res[r["path"]], n)]
        if len(pts) >= 20 and len({y for _, y in pts}) == 2:
            lr = LogisticRegression(C=1e4).fit([[s] for s, _ in pts], [y for _, y in pts])
            cal[n] = {"a": round(float(lr.coef_[0][0]), 4), "b": round(float(lr.intercept_[0]), 4),
                      "n": len(pts)}
    (ROOT / "configs" / "calibration.yaml").write_text(
        "# Written by scripts/eval.py --calibrate from the calib split ONLY.\n"
        "# score' = sigmoid(a * score + b), applied in scoring/composite.py\n"
        + yaml.safe_dump(cal, sort_keys=True), encoding="utf-8")
    config.cfg.cache_clear()

    note = (f"{datetime.now():%Y-%m-%d %H:%M} — calibrated {', '.join(cal) or 'nothing'} on "
            f"{len(calib)} calib rows (quality=orig) → configs/calibration.yaml.")
    W = config.cfg("weights")["image"]
    img = [n for n in cal if W.get(n, 0) > 0]
    y = [r["label"] == "fake" for r in calib]
    if img and len(set(y)) == 2:
        X = np.array([[res[r["path"]]["signals"][n][0] if usable(res[r["path"]], n) else 0.5
                       for n in img] for r in calib])
        w = np.clip(LogisticRegression(C=1.0).fit(X, y).coef_[0], 0, None)
        total = sum(W[n] for n in img)
        if w.sum() > 0:
            sug = {n: round(float(v / w.sum() * total), 3) for n, v in zip(img, w)}
            note += (f" Suggested image-lane weights (NOT applied — edit weights.yaml by hand, "
                     f"then make eval): {sug}.")
    print(note)
    return note


def score_docs(a):
    from claimshield.pipeline import score_document

    path = ROOT / "data" / "docs" / "manifest.csv"
    if a.no_docs or not path.exists():
        return []
    docs = list(csv.DictReader(open(path, encoding="utf-8")))
    if a.subset:
        docs = random.Random(0).sample(docs, min(len(docs), max(20, a.subset // 5)))
    out = []
    for i, d in enumerate(docs):
        data = (ROOT / d["path"]).read_bytes()
        f = CACHE / f"doc_{hashlib.sha256(data).hexdigest()}.json"
        if not f.exists():
            r = score_document(str(ROOT / d["path"]))
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"band": r.claim.band, "overall": r.claim.overall}))
        out.append({**d, **json.loads(f.read_text())})
        if i % 50 == 0:
            print(f"  docs {i}/{len(docs)}", flush=True)
    return out


def run(a):
    rows = list(csv.DictReader(open(ROOT / a.manifest, encoding="utf-8")))
    rows = [r for r in rows if r["split"] != "train" and (a.calibrate or r["split"] != "calib")]
    if a.subset:
        rows = random.Random(0).sample(rows, min(a.subset, len(rows)))
    names = a.signals.split(",") if a.signals else ALL
    fns, res, t0 = _checks(), {}, time.perf_counter()
    for i, r in enumerate(rows):
        res[r["path"]] = score_row(r, names, fns, a.impls)
        if i % 50 == 0:
            print(f"  images {i}/{len(rows)}  {time.perf_counter() - t0:.0f} s", flush=True)
    note = calibrate(rows, res, names) if a.calibrate else ""
    report([r for r in rows if r["split"] != "calib"], res, names, score_docs(a), a, note)
    print(f"eval done in {time.perf_counter() - t0:.0f} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--manifest", default="data/generated/manifest.csv")
    ap.add_argument("--out", default="reports/eval_latest.md")
    ap.add_argument("--subset", type=int)
    ap.add_argument("--signals", help="comma list; default: all image signals")
    ap.add_argument("--impls", default="trufor,fallback", help="localizers for the IoU row")
    ap.add_argument("--calibrate", action="store_true", help="fit sigmoids on calib, then report")
    ap.add_argument("--no-docs", action="store_true")
    a = ap.parse_args()
    a.impls = a.impls.split(",")
    if a.dry:
        sys.exit(0 if dry(a.manifest) else 1)
    run(a)


if __name__ == "__main__":
    main()
