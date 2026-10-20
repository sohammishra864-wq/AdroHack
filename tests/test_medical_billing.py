"""Health-insurance upcoding check: each rule on known text, then a round trip through real
generated PDFs: clean reports pass, every upcoded report is flagged by the rule it breaks."""
import random
import sys
from pathlib import Path

import pytest

from claimshield.signals.documents import medical_billing as mb

BILL = """St. Anne's Multispeciality Hospital
DISCHARGE SUMMARY
Patient: Meera Pillai
Admitted: 05/07/2026
Discharged: {dis}/07/2026
Diagnosis
{dx} (ICD-10 {code})
Charges
Room charges (per day) {room}
Consultation 1,500.00
{proc} 8,120.00
Total (INR) 99,999.00"""


def bill(code="S06.0", dx="Concussion", dis="07", room="9,000.00", proc="CT scan"):
    return BILL.format(code=code, dx=dx, dis=dis, room=room, proc=proc)


def test_clean_bill_fits():
    s = mb.run(bill(), "medical")          # 2-day concussion stay, CT, 4,500/day room
    assert s.score == 0.1 and "concussion" in s.reason


def test_procedure_the_diagnosis_does_not_need():
    s = mb.run(bill(proc="Surgery"), "medical")
    assert s.score == 0.85 and "Surgery billed for concussion" in s.reason


def test_stay_too_long():
    s = mb.run(bill(dis="12", room="31,500.00"), "medical")   # 7 days, still 4,500/day
    assert s.score == 0.6 and "7-day stay" in s.reason


def test_more_days_billed_than_stayed():
    s = mb.run(bill(room="27,000.00"), "medical")              # 2 days → 13,500/day
    assert s.score == 0.7 and "per day" in s.reason


def test_not_applicable_outside_the_table_or_for_invoices():
    assert not mb.run(bill(code="T14.9"), "medical").applicable
    assert not mb.run(bill(), "invoice").applicable


def test_generated_reports_round_trip(tmp_path):
    pytest.importorskip("pikepdf")
    pytest.importorskip("pdfplumber")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "gen"))
    import invoices
    import medical

    from claimshield.signals.documents import doc_type, pdf_structure

    def score(kind, i):
        page, producer, created, _ = medical.report(i, random.Random(f"t/{kind}/{i}"), kind)
        f = tmp_path / f"{kind}_{i}.pdf"
        invoices.write_pdf(f, page.items, producer, created)
        text = pdf_structure.text_of(f.read_bytes())
        assert doc_type.classify(text) == "medical"
        return mb.run(text, "medical")

    assert all(score(None, i).score == 0.1 for i in range(40))                 # no false alarms
    for kind, want in (("procedure", 0.85), ("stay", 0.6), ("days", 0.7)):
        assert all(score(kind, i).score >= want for i in range(20)), kind
