"""D2 templates: field checks in code on the document text (text layer or OCR).

field_arithmetic  line items → subtotal → tax → total (invoice, medical bills)
field_dates       ordered date pairs per doc type; no date in the future
field_format      invoice-number shape, ICD-10 code pattern, passport MRZ check digits
"""
from __future__ import annotations

import re
from datetime import date, datetime

from ... import config
from ...contracts import Signal

AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{2,3})+(?:\.\d{2})?|\d+\.\d{2})(?![\d,])")
DATE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]{2} \d{4})\b")
DATE_FMTS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y")  # day-first (Indian documents)
TAX = re.compile(r"\b(gst|cgst|sgst|igst|vat|tax)\b", re.I)
ICD10 = re.compile(r"ICD-?10\W*([A-Z0-9.]+)", re.I)
ICD10_OK = re.compile(r"^[A-TV-Z]\d[0-9AB](\.[0-9A-TV-Z]{1,4})?$")
# (earlier label keyword, later label keyword) per doc type; labels are the text before a date
DATE_ORDER = {"invoice": [("date", "due")],
              "medical": [("admi", "discharg")],
              "id": [("birth", "issue"), ("issue", "expir")]}


def money(s: str) -> float:
    return float(s.replace(",", ""))


def parse_date(s: str) -> date | None:
    for f in DATE_FMTS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def close(a: float, b: float) -> bool:
    C = config.cfg("thresholds")["documents"]
    return abs(a - b) <= max(C["amount_tol_abs"], C["amount_tol_rel"] * max(abs(a), abs(b)))


def arithmetic(lines: list[str]) -> tuple[list[str], list[str]]:
    """→ (checks that ran, problems). Items are money lines before the first subtotal/tax/total."""
    items, subtotal, tax, total, rates, ran, bad = [], None, 0.0, None, [], [], []
    for ln in lines:
        amts = AMOUNT.findall(ln)
        if not amts:
            continue
        low = ln.lower()
        if re.search(r"sub\s?-?total", low):
            subtotal = money(amts[-1])
        elif TAX.search(ln):
            tax += money(amts[-1])
            rates += [float(r) for r in re.findall(r"(\d+(?:\.\d+)?)\s*%", ln)]
        elif re.search(r"\btotal\b|amount due|balance due", low):
            total = money(amts[-1])
        elif subtotal is None and total is None:
            items.append(money(amts[-1]))
            q = re.search(r"\b(\d{1,4})\s+" + re.escape(amts[-2]), ln) if len(amts) >= 2 else None
            if q:
                ran.append("qty × unit")
                if not close(int(q.group(1)) * money(amts[-2]), money(amts[-1])):
                    bad.append(f"line \"{ln.strip()}\": {q.group(1)} × {amts[-2]} ≠ {amts[-1]}")
    if items and subtotal is not None:
        ran.append("items = subtotal")
        if not close(sum(items), subtotal):
            bad.append(f"line items add up to {sum(items):,.2f}, subtotal says {subtotal:,.2f}")
    base = subtotal if subtotal is not None else (sum(items) if items else None)
    if base is not None and total is not None:
        ran.append("subtotal + tax = total")
        if not close(base + tax, total):
            bad.append(f"{base:,.2f} + tax {tax:,.2f} = {base + tax:,.2f}, total says {total:,.2f}")
    allowed = config.cfg("thresholds")["documents"]["tax_rates"]
    for r in rates:
        ran.append("tax rate")
        if r not in allowed:
            bad.append(f"tax rate {r:g}% is not a valid slab {allowed}")
    if len(rates) == 1 and base is not None and tax:
        ran.append("tax amount")
        if not close(base * rates[0] / 100, tax):
            bad.append(f"{rates[0]:g}% of {base:,.2f} is {base * rates[0] / 100:,.2f}, not {tax:,.2f}")
    return ran, bad


def dated(lines: list[str]) -> dict[str, date]:
    out = {}
    for ln in lines:
        m = DATE.search(ln)
        d = parse_date(m.group(1)) if m else None
        if d:
            out[ln[:m.start()].strip(" :").lower() or f"line{len(out)}"] = d
    return out


def dates(lines: list[str], doc_type: str, today: date | None = None) -> tuple[list[str], list[str]]:
    today, found, ran, bad = today or date.today(), dated(lines), [], []
    for label, d in found.items():
        if any(k in label for k in ("due", "expir", "valid")):
            continue  # these are meant to be in the future
        ran.append("not in future")
        if d > today:
            bad.append(f"{label or 'a date'} {d:%d %b %Y} is in the future")
    for a, b in DATE_ORDER.get(doc_type, []):
        ka = next((k for k in found if a in k and b not in k), None)
        kb = next((k for k in found if b in k), None)
        if ka and kb:
            ran.append(f"{ka} ≤ {kb}")
            if found[ka] > found[kb]:
                bad.append(f"\"{ka}\" {found[ka]:%d %b %Y} is after \"{kb}\" {found[kb]:%d %b %Y}")
    return ran, bad


def mrz_digit(s: str) -> str:
    v = [int(c) if c.isdigit() else ord(c) - 55 if c.isalpha() else 0 for c in s]
    return str(sum(x * (7, 3, 1)[i % 3] for i, x in enumerate(v)) % 10)


def formats(text: str, doc_type: str) -> tuple[list[str], list[str]]:
    ran, bad = [], []
    if doc_type == "invoice":
        m = re.search(r"(?:invoice|inv)\s*(?:no\.?|number|#)\s*:?\s*(\S+)", text, re.I)
        if m:
            ran.append("invoice number")
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9/\-]{2,19}", m.group(1), re.I):
                bad.append(f"invoice number \"{m.group(1)}\" has an unusual format")
    if doc_type == "medical":
        for code in ICD10.findall(text):
            ran.append("ICD-10")
            if not ICD10_OK.match(code.rstrip(".)")):
                bad.append(f"\"{code}\" is not a valid ICD-10 code pattern")
    if doc_type == "id":
        for ln in text.splitlines():
            ln = ln.replace(" ", "")
            if len(ln) == 44 and re.fullmatch(r"[A-Z0-9<]+", ln) and ln[9].isdigit():
                ran.append("MRZ check digits")  # TD3 line 2: document no., birth, expiry
                for what, a, b in (("document number", 0, 9), ("date of birth", 13, 19),
                                   ("expiry", 21, 27)):
                    if mrz_digit(ln[a:b]) != ln[b]:
                        bad.append(f"MRZ check digit for {what} does not match")
    return ran, bad


def _signal(name, ran, bad, what, from_ocr, hit=(0.85, 0.8)) -> Signal:
    if not ran:
        return Signal(name, None, 0.0, f"Not applicable: no {what} found to check.",
                      applicable=False)
    ev = {"checks": ran, "problems": bad}
    if bad:
        s, c = hit
        c = c * 0.6 if from_ocr else c  # OCR misreads can fake a mismatch
        return Signal(name, s, c, bad[0][0].upper() + bad[0][1:] + "." +
                      (f" ({len(bad) - 1} more)" if len(bad) > 1 else ""), ev)
    return Signal(name, 0.15, 0.5 if not from_ocr else 0.3,
                  f"All {len(ran)} {what} checks passed.", ev)


def run(text: str, doc_type: str, from_ocr: bool = False) -> list[Signal]:
    lines = text.splitlines()
    return [_signal("field_arithmetic", *arithmetic(lines), "amounts", from_ocr),
            _signal("field_dates", *dates(lines, doc_type), "dates", from_ocr, (0.75, 0.7)),
            _signal("field_format", *formats(text, doc_type), "codes or numbers", from_ocr, (0.6, 0.5))]


NAME_LABEL = re.compile(r"^\s*(name|patient(?: name)?|customer|bill to|billed to|insured|"
                        r"claimant|surname and given names?)\s*[:\-]?\s*(.*)$", re.I)


def person_name(text: str) -> str | None:
    """Claimant name for the claim-level check: passport MRZ first, then a labelled line
    (the name may sit on the line after a bare "Bill to")."""
    lines = [ln.strip() for ln in text.splitlines()]
    for ln in lines:
        s = ln.replace(" ", "")
        if len(s) == 44 and s.startswith("P") and "<<" in s:
            surname, _, given = s[5:].partition("<<")
            return " ".join((given.replace("<", " ").strip() + " " + surname.replace("<", " ")).split()).title()
    for i, ln in enumerate(lines):
        m = NAME_LABEL.match(ln)
        if m:
            rest = m.group(2).strip() or (lines[i + 1] if i + 1 < len(lines) else "")
            if re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,60}", rest):
                return rest
    return None


def invoice_date(text: str) -> date | None:
    """The document's own date (not a due date)."""
    return next((d for k, d in dated(text.splitlines()).items()
                 if "date" in k and not any(x in k for x in ("due", "birth", "expir"))), None)
