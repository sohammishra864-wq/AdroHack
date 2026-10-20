"""Document lane. Pure-logic tests run anywhere; the end-to-end ones need pikepdf +
pdfplumber (+ cv2 for the pipeline) and use scripts/gen to make fresh PDFs."""
import random
import sys
from datetime import date
from pathlib import Path

import pytest

from claimshield.signals.documents import doc_type, fields, ocr, pdf_structure

ROOT = Path(__file__).resolve().parents[1]
INVOICE = """Speedline Auto Repairs
INVOICE
No. INV-202600001
Date: 12/03/2026
Due: 11/04/2026
Description Qty Unit Amount
Rear bumper replacement 2 18,500.00 37,000.00
Paint and blend 1 6,500.00 6,500.00
Subtotal 43,500.00
GST 18% 7,830.00
Total (INR) 51,330.00"""
MEDICAL = """Lotus Medical Institute
DISCHARGE SUMMARY
Patient: A
Admitted: 2026-03-02
Discharged: 2026-03-05
Fracture of patella (ICD-10 S82.0)
X-ray 1,200.00
Surgery 45,000.00
Total (INR) 46,200.00"""
MRZ = ("P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
       "L898902C36UTO7408122F1204159ZE184226B<<<<<10\nPassport  Date of birth")  # ICAO specimen


def by_name(sigs):
    return {s.name: s for s in sigs}


def test_doc_type_rules():
    assert doc_type.classify(INVOICE) == "invoice"
    assert doc_type.classify(MEDICAL) == "medical"
    assert doc_type.classify(MRZ) == "id"
    assert doc_type.classify("hello world") == "other"


def test_clean_invoice_passes_every_field_check():
    s = by_name(fields.run(INVOICE, "invoice"))
    assert all(x.score < 0.35 and x.applicable for x in s.values())


def test_edited_total_breaks_arithmetic():
    s = by_name(fields.run(INVOICE.replace("51,330.00", "91,330.00"), "invoice"))
    assert s["field_arithmetic"].score >= 0.65 and "91,330.00" in s["field_arithmetic"].reason


def test_bad_tax_slab_and_qty_line():
    t = INVOICE.replace("GST 18% 7,830.00", "GST 17% 7,395.00").replace("1 6,500.00 6,500.00", "2 6,500.00 6,500.00")
    probs = fields.run(t, "invoice")[0].evidence["problems"]
    assert any("17%" in p for p in probs) and any("2 × 6,500.00" in p for p in probs)


def test_dates_order_and_future():
    ran, bad = fields.dates(["Date: 12/03/2026", "Due: 01/03/2026"], "invoice", date(2026, 9, 30))
    assert bad and "after" in bad[0]
    _, bad = fields.dates(["Admitted: 2027-01-01", "Discharged: 2027-01-03"], "medical", date(2026, 9, 30))
    assert any("future" in b for b in bad)
    _, bad = fields.dates(["Date: 12/03/2026", "Due: 11/12/2026"], "invoice", date(2026, 9, 30))
    assert bad == []  # a due date may be in the future


def test_icd10_and_mrz_formats():
    assert fields.run(MEDICAL, "medical")[2].score < 0.35
    assert fields.run(MEDICAL.replace("S82.0", "U99.X!"), "medical")[2].score >= 0.5
    assert fields.run(MRZ, "id")[2].score < 0.35
    assert "date of birth" in fields.run(MRZ.replace("7408122", "7408125"), "id")[2].reason


def test_nothing_to_check_is_not_applicable():
    assert not fields.run("just words", "other")[0].applicable


def test_ocr_dips_and_line_rebuild():
    ws = [{"text": "Total", "conf": 95, "page": 0, "box": (0, 100, 50, 120)},
          {"text": "91,330.00", "conf": 41, "page": 0, "box": (60, 102, 140, 121)},
          {"text": "Date", "conf": 90, "page": 0, "box": (0, 10, 40, 30)}]
    assert ocr.text_of(ws) == "Date\nTotal 91,330.00"
    s = ocr.run(ws)
    assert s.score >= 0.5 and s.evidence["dips"][0]["text"] == "91,330.00"
    assert not ocr.run([ws[0]]).applicable


def test_revisions_and_diff():
    one = b"%PDF-1.4 a %%EOF\n"
    two = one + b"update %%EOF\n"
    assert len(pdf_structure.revisions(one)) == 1
    assert pdf_structure.revisions(two)[0] == b"%PDF-1.4 a %%EOF"
    assert pdf_structure.diff_rows("a\nTotal 1\nb", "a\nTotal 9\nb") == [("Total 1", "Total 9")]


def test_producer_and_fonts():
    s = pdf_structure.producer({"/Producer": "iLovePDF", "/CreationDate": "D:20260301120000",
                                "/ModDate": "D:20260315120000"})
    assert s.score >= 0.65 and "14 days" in s.reason
    assert pdf_structure.producer({"/Producer": "Microsoft Word 2019"}).score < 0.35
    chars = [{"text": c, "fontname": "Helvetica"} for c in "Total amount due " * 20]
    chars += [{"text": c, "fontname": "ABCDEF+Arial"} for c in "91,3"]
    assert pdf_structure.fonts(chars).score >= 0.65
    assert pdf_structure.fonts(chars[:-4]).score < 0.35


@pytest.fixture
def gen(tmp_path, monkeypatch):
    pytest.importorskip("pikepdf")
    pytest.importorskip("pdfplumber")
    sys.path.insert(0, str(ROOT / "scripts" / "gen"))
    import invoices

    monkeypatch.chdir(tmp_path)
    page, producer, created, extra = invoices.invoice(0, random.Random(0))
    invoices.save("invoice_0000", page, producer, created, extra)
    return invoices.OUT / "invoice_0000.pdf", page.fields["total"]["text"], created


def test_time_machine_finds_the_edit(gen, tmp_path):
    import tamper_pdf

    src, old, created = gen
    dst = tmp_path / "t.pdf"
    tamper_pdf.incremental(src, dst, old, "99,999.00", created.replace(month=created.month % 12 + 1))
    clean = by_name(pdf_structure.run(src.read_bytes())[0])
    edited = by_name(pdf_structure.run(dst.read_bytes())[0])
    assert clean["pdf_incremental_update"].score < 0.35
    s = edited["pdf_incremental_update"]
    assert s.score >= 0.65 and any(old in a and "99,999.00" in b for a, b in s.evidence["diff"])


def test_score_document_ranks_tampered_above_clean(gen, tmp_path):
    pytest.importorskip("cv2")
    import tamper_pdf

    from claimshield.pipeline import score_document

    src, old, created = gen
    dst = tmp_path / "rw.pdf"
    tamper_pdf.producer_rewrite(src, dst, old, "99,999.00", created, random.Random(0))
    clean, bad = score_document(str(src)), score_document(str(dst))
    assert clean.doc_type == "invoice" and not clean.from_ocr
    assert bad.claim.document_score > clean.claim.document_score
    assert bad.claim.band in ("MEDIUM", "HIGH")
