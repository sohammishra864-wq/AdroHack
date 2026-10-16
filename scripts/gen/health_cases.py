"""Health-insurance demo cases → data/cases/h1_first … h4_followup.

  h1_first     clean discharge summary, St. Anne's, Meera Pillai, admitted 5 Jul 2026
  h2_repeat    the SAME stay claimed again (same hospital, patient, admission date)
                                                    → cross_claim "same hospital stay"
  h3_upcoded   another hospital + patient, a procedure the diagnosis doesn't need
                                                    → medical_billing
  h4_followup  LEGIT: Meera Pillai back at St. Anne's in September (a new stay)
                                                    → must stay LOW (only a 0.3 link)
Score them in that order. Also clears the cross-claim memory (--keep-memory to skip).
Usage: python scripts/gen/health_cases.py
"""
import argparse
import datetime as dt
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import invoices  # noqa: E402  (same folder)
import medical  # noqa: E402
from claimshield import memory  # noqa: E402

CASES = ROOT / "data" / "cases"
PATIENT = "Meera Pillai"
STAY = dt.date(2026, 7, 5)


def write(d: Path, i: int, title: str, **kw) -> Path:
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    page, producer, created, _ = medical.report(i, random.Random(f"health/{i}"), **kw)
    invoices.write_pdf(d / "medical_report.pdf", page.items, producer, created)
    (d / "case.json").write_text(json.dumps({"title": title}), encoding="utf-8")
    return d


def build(out: Path = CASES) -> list[Path]:
    return [write(out / "h1_first", 7001, "Health 1: first hospital claim", hospital=0, patient=PATIENT,
                  admitted=STAY),
            write(out / "h2_repeat", 7002, "Health 2: same stay claimed again", hospital=0, patient=PATIENT,
                  admitted=STAY),
            write(out / "h3_upcoded", 7003, "Health 3: procedure the diagnosis doesn't need",
                  upcode="procedure", hospital=2, patient="Daniel Brooks"),
            write(out / "h4_followup", 7004, "Health 4 (legit): follow-up stay, new dates", hospital=0,
                  patient=PATIENT, admitted=dt.date(2026, 9, 14))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-memory", action="store_true")
    a = ap.parse_args()
    for d in build():
        print(f"wrote {d.relative_to(ROOT)}")
    if not a.keep_memory:
        print(f"cross-claim memory cleared ({memory.reset()} rows)")
    print("Score h1_first → h2_repeat → h3_upcoded → h4_followup in that order.")


if __name__ == "__main__":
    main()
