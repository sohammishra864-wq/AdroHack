"""Measure the health-insurance billing check on generated discharge summaries: real PDFs,
read back the way the app reads them → reports/medical_billing.md.
Clean reports should pass; each upcode kind should be flagged. Synthetic: the generator and the
check share the CARE table, so this measures the parsing + rules end to end, not real-world
accuracy. Say so when quoting it.
Usage: python scripts/eval_medical.py [--n 200]
"""
import argparse
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts" / "gen")]
import invoices  # noqa: E402
import medical  # noqa: E402
from claimshield.signals.documents import doc_type, medical_billing, pdf_structure  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=str(ROOT / "reports" / "medical_billing.md"))
    a = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for kind in (None, *medical.UPCODES):
            flagged = typed = 0
            for i in range(a.n):
                page, producer, created, _ = medical.report(i, random.Random(f"eval/{kind}/{i}"), kind)
                f = Path(d) / "r.pdf"
                invoices.write_pdf(f, page.items, producer, created)
                text = pdf_structure.text_of(f.read_bytes())
                kindof = doc_type.classify(text)
                typed += kindof == "medical"
                s = medical_billing.run(text, kindof)
                flagged += s.score is not None and s.score >= 0.5
            rows.append((kind or "clean", a.n, typed, flagged))
    lines = ["# Medical billing check (health-insurance upcoding)", "",
             f"Generated discharge summaries, {a.n} per row, real PDFs read back with pdfplumber.",
             "Synthetic: generator and check share the care table, so this measures parsing + rules end",
             "to end, not real-world accuracy.", "",
             "| reports | n | read as medical | flagged (score ≥ 0.5) | rate |", "|---|---|---|---|---|"]
    for kind, n, typed, flagged in rows:
        lines.append(f"| {kind} | {n} | {typed} | {flagged} | {flagged / n:.1%} |")
    clean = rows[0]
    caught = sum(r[3] for r in rows[1:])
    lines += ["", f"False-alarm rate on clean reports: **{clean[3] / clean[1]:.1%}**. "
              f"Upcoded caught: **{caught}/{a.n * 3}**."]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
