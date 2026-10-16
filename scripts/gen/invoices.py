"""Clean invoice PDFs from several vendor templates → data/docs/clean/invoice_<n>.pdf + .json.

The .json sidecar holds every field's text and position (points, origin bottom-left), which
tamper_pdf.py uses to edit a field and eval uses as field-level ground truth. Written with
pikepdf only (standard Type1 fonts, no font files), so no extra dependency.
Usage: python scripts/gen/invoices.py [--n 100]
"""
import argparse
import datetime as dt
import json
import random
from pathlib import Path

import pikepdf
from pikepdf import Dictionary, Name

OUT = Path("data/docs/clean")
W, H = 595, 842  # A4 in points
FONTS = {"F1": "Helvetica", "F2": "Helvetica-Bold", "F3": "Times-Roman", "F4": "Times-Bold",
         "F5": "Courier", "F6": "Courier-Bold"}
NAMES = ["Asha Verma", "Rahul Nair", "Priya Iyer", "Daniel Brooks", "Meera Pillai",
         "Arjun Rao", "Sara Khan", "Vikram Shah", "Emily Carter", "Kiran Das"]
VENDORS = [  # name, regular/bold font, left margin, date format, producer, line items
    ("Speedline Auto Repairs", ("F1", "F2"), 50, "%d/%m/%Y", "Microsoft Word 2019",
     [("Rear bumper replacement", 18000), ("Paint and blend", 6500), ("Labour (hours)", 900),
      ("Headlight assembly", 7400), ("Wheel alignment", 1200), ("Sensor recalibration", 2500)]),
    ("HomeFix Plumbing & Restoration", ("F3", "F4"), 60, "%Y-%m-%d", "LibreOffice 7.6",
     [("Leak detection", 2500), ("Pipe section replacement", 4800), ("Drywall repair", 7200),
      ("Dehumidifier rental (days)", 600), ("Repainting", 5400)]),
    ("CityTech Device Care", ("F5", "F6"), 45, "%d %b %Y", "Zoho Invoice",
     [("Screen assembly", 14500), ("Battery replacement", 3900), ("Diagnostics", 800),
      ("Logic board repair", 11800), ("Data recovery", 6000)]),
    ("Northgate Glass & Glazing", ("F1", "F2"), 70, "%d-%m-%Y", "QuickBooks Online",
     [("Windscreen replacement", 16500), ("Moulding kit", 1400), ("Callout fee", 750),
      ("ADAS camera calibration", 4200)]),
]
TAX_RATES = (5, 12, 18)


def money(x):
    return f"{x:,.2f}"


def pdf_date(d):
    return f"D:{d:%Y%m%d%H%M%S}+05'30'"


def esc(t):
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, items, producer, created):
    """items: ("text", x, y, size, font, text) or ("line", x1, y1, x2, y2)."""
    ops = []
    for it in items:
        if it[0] == "line":
            ops.append("%d %d m %d %d l S" % it[1:])
        else:
            _, x, y, size, font, text = it
            ops.append(f"BT /{font} {size} Tf {x} {y} Td ({esc(text)}) Tj ET")
    pdf = pikepdf.new()
    fonts = Dictionary({f"/{k}": Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                             BaseFont=Name(f"/{v}")) for k, v in FONTS.items()})
    pdf.pages.append(pikepdf.Page(Dictionary(
        Type=Name.Page, MediaBox=[0, 0, W, H], Resources=Dictionary(Font=fonts),
        Contents=pdf.make_stream("\n".join(ops).encode("latin-1")))))
    pdf.docinfo[Name.Producer] = producer
    pdf.docinfo[Name.CreationDate] = pdf.docinfo[Name.ModDate] = pdf_date(created)
    # classic xref table (no object streams) so tamper_pdf can append an incremental update
    pdf.save(path, object_stream_mode=pikepdf.ObjectStreamMode.disable)


class Page:
    """Collects items and remembers where each named field was drawn."""
    def __init__(self):
        self.items, self.fields = [], {}

    def text(self, x, y, size, font, text, field=None):
        self.items.append(("text", x, y, size, font, text))
        if field:
            self.fields[field] = {"text": text, "x": x, "y": y, "size": size, "font": font}

    def line(self, x1, y1, x2, y2):
        self.items.append(("line", x1, y1, x2, y2))


def invoice(i, rng, vendor=None, customer=None, vin=None):
    """vendor (index into VENDORS) / customer / vin pin those fields for the fraud-ring demo
    (scripts/gen/ring_cases.py). Left at None, the output is unchanged from before."""
    name, (reg, bold), L, datefmt, producer, catalogue = (rng.choice(VENDORS) if vendor is None
                                                          else VENDORS[vendor])
    date = dt.date(2026, 1, 1) + dt.timedelta(days=rng.randrange(0, 240))
    p = Page()
    p.text(L, 780, 18, bold, name, "vendor")
    p.text(L, 762, 9, reg, f"{rng.randrange(1, 300)} Industrial Estate, Pune 4110{rng.randrange(10, 99)}")
    p.text(W - 200, 780, 16, bold, "INVOICE")
    p.text(W - 200, 760, 10, reg, f"No. INV-{2026}{i:05d}", "invoice_no")
    p.text(W - 200, 746, 10, reg, "Date: " + date.strftime(datefmt), "date")
    p.text(W - 200, 732, 10, reg, "Due: " + (date + dt.timedelta(days=30)).strftime(datefmt), "due_date")
    p.text(L, 715, 10, bold, "Bill to")
    p.text(L, 701, 10, reg, customer or rng.choice(NAMES), "customer")
    p.text(L, 687, 10, reg, f"Claim ref CLM-{rng.randrange(100000, 999999)}", "claim_ref")
    if vin:
        p.text(L, 673, 10, reg, f"VIN: {vin}", "vin")
    y = 650
    for x, h in ((L, "Description"), (330, "Qty"), (390, "Unit"), (480, "Amount")):
        p.text(x, y, 10, bold, h)
    p.line(L, y - 5, W - L, y - 5)
    subtotal = 0
    for k, (desc, unit) in enumerate(rng.sample(catalogue, rng.randint(2, len(catalogue)))):
        qty = rng.randint(1, 4)
        unit = round(unit * rng.uniform(0.8, 1.25), -1)
        y -= 20
        p.text(L, y, 10, reg, desc, f"item{k}_desc")
        p.text(330, y, 10, reg, str(qty), f"item{k}_qty")
        p.text(390, y, 10, reg, money(unit), f"item{k}_unit")
        p.text(480, y, 10, reg, money(qty * unit), f"item{k}_amount")
        subtotal += qty * unit
    rate = rng.choice(TAX_RATES)
    tax = round(subtotal * rate / 100, 2)
    p.line(L, y - 10, W - L, y - 10)
    for label, val, field, font in (("Subtotal", subtotal, "subtotal", reg),
                                    (f"GST {rate}%", tax, "tax", reg),
                                    ("Total (INR)", subtotal + tax, "total", bold)):
        y -= 20
        p.text(390, y, 10, font, label)
        p.text(480, y, 10, font, money(val), field)
    p.text(L, 80, 8, reg, "Thank you for your business. Payment by bank transfer within 30 days.")
    created = dt.datetime.combine(date, dt.time(rng.randrange(9, 18), rng.randrange(60)))
    return p, producer, created, {"tax_rate": rate}


def save(stem, page, producer, created, extra):
    OUT.mkdir(parents=True, exist_ok=True)
    write_pdf(OUT / f"{stem}.pdf", page.items, producer, created)
    meta = {"fields": page.fields, "producer": producer, "created": created.isoformat(), **extra}
    (OUT / f"{stem}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    n = ap.parse_args().n
    for i in range(n):
        save(f"invoice_{i:04d}", *invoice(i, random.Random(f"invoice/{i}")))
    print(f"wrote {n} invoices to {OUT}")


if __name__ == "__main__":
    main()
