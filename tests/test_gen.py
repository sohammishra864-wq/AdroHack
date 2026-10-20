"""Phase 2 data scripts: manifest split grouping, eval --dry checks, incremental-update PDFs."""
import csv
import importlib.util
import random
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "gen"))
spec = importlib.util.spec_from_file_location("eval_script", ROOT / "scripts" / "eval.py")
eval_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_script)


def test_manifest_keeps_seed_groups_together_and_passes_dry(tmp_path, monkeypatch):
    import manifest
    import rows

    monkeypatch.chdir(tmp_path)
    seeds = []
    for i in range(40):
        p = Path("data/seeds") / f"s{i}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 48)).save(p)
        seeds.append(p)
    for fam in ("sd15", "flux"):
        d = Path("data/generated", fam, "img2img")
        d.mkdir(parents=True)
        out = []
        for i, s in enumerate(seeds):
            Image.new("RGB", (64, 48)).save(d / f"{i}.jpg")
            out.append({"path": d / f"{i}.jpg", "label": "fake", "family": fam, "attack": "img2img",
                        "quality": "orig", "seed_path": s})
        rows.write(d, out)
    manifest.main()

    got = list(csv.DictReader(open(manifest.OUT, encoding="utf-8")))
    assert len(got) == 120
    assert {r["split"] for r in got if r["family"] == "flux"} == {"test"}
    monkeypatch.setattr(eval_script, "ROOT", tmp_path)
    assert eval_script.check_images(got) == []

    r = next(r for r in got if r["family"] == "sd15")  # held-out rows are exempt
    r["split"] = "calib" if r["split"] != "calib" else "train"  # break a seed group
    assert any("leaks" in e for e in eval_script.check_images(got))


def test_incremental_update_keeps_the_old_revision(tmp_path, monkeypatch):
    pikepdf = pytest.importorskip("pikepdf")
    import invoices
    import tamper_pdf

    monkeypatch.chdir(tmp_path)
    page, producer, created, extra = invoices.invoice(0, random.Random(0))
    invoices.save("invoice_0000", page, producer, created, extra)
    src, dst = invoices.OUT / "invoice_0000.pdf", tmp_path / "t.pdf"
    old = page.fields["total"]["text"]
    tamper_pdf.incremental(src, dst, old, "99,999.00", created)

    raw = dst.read_bytes()
    assert len(re.findall(rb"startxref", raw)) == 2
    with pikepdf.open(dst) as pdf:
        assert b"(99,999.00)" in pdf.pages[0].obj.Contents.read_bytes()
    first = raw[:raw.index(b"%%EOF") + 5]  # truncate at the first revision → original text
    (tmp_path / "v1.pdf").write_bytes(first)
    with pikepdf.open(tmp_path / "v1.pdf") as pdf:
        assert f"({old})".encode() in pdf.pages[0].obj.Contents.read_bytes()
