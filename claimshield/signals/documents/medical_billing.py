"""Medical billing vs diagnosis (health-insurance upcoding). On a discharge summary / hospital
bill: (1) a procedure billed that the diagnosis does not normally need (surgery for a
concussion), (2) a stay longer than that diagnosis normally needs, (3) per-day charges whose
implied daily rate is out of band (more days billed than the patient stayed).

The care table is a small, hand-written reference for the diagnoses we generate, NOT a clinical
guideline. A code outside the table → not applicable (no opinion), never "fraud".
# ponytail: 7-code table; a real deployment would load a payer's procedure-diagnosis edits (NCCI-like).
"""
from __future__ import annotations

import re

from ...contracts import Signal
from . import fields

NAME = "medical_billing"
# ICD-10: (diagnosis in words, procedures it normally needs beyond the basics, longest normal stay)
CARE = {
    "S82.0": ("fracture of the patella", {"x-ray", "ct scan", "surgery", "physiotherapy"}, 7),
    "S52.5": ("fracture of the lower radius", {"x-ray", "surgery", "physiotherapy"}, 5),
    "S06.0": ("concussion", {"ct scan"}, 3),
    "S13.4": ("neck sprain", {"x-ray", "physiotherapy"}, 2),
    "S43.0": ("shoulder dislocation", {"x-ray", "physiotherapy"}, 3),
    "S22.3": ("rib fracture", {"x-ray", "ct scan"}, 5),
    "S83.5": ("knee ligament sprain", {"x-ray", "surgery", "physiotherapy"}, 4),
}
PROCEDURES = ("surgery", "ct scan", "x-ray", "physiotherapy")   # basics (room, nursing, consultation, pharmacy) always fit
PER_DAY = {"room charges": (1500, 8000), "nursing": (600, 3000)}  # INR/day band for a private hospital
ICD = re.compile(r"ICD-10\s*([A-TV-Z]\d{2}(?:\.\d{1,4})?)", re.I)
CHARGE = re.compile(r"^(.*?)\s+([\d,]+\.\d{2})\s*$")


def charges(lines: list[str]) -> list[tuple[str, float]]:
    out = []
    for ln in lines:
        m = CHARGE.match(ln.strip())
        if m and not m.group(1).lower().startswith(("total", "subtotal")):
            out.append((m.group(1).strip(), fields.money(m.group(2))))
    return out


def check(text: str) -> tuple[str, str, list[tuple[float, str]]] | None:
    """→ (code, diagnosis, [(score, problem), …]) or None when the code isn't in CARE."""
    m = ICD.search(text)
    code = m.group(1).upper() if m else None
    if code not in CARE:
        return None
    dx, allowed, max_days = CARE[code]
    lines = text.splitlines()
    found = fields.dated(lines)
    adm = next((d for k, d in found.items() if k.startswith("admi")), None)
    dis = next((d for k, d in found.items() if k.startswith("discharg")), None)
    days = (dis - adm).days if adm and dis and dis >= adm else None
    bad = []
    for desc, amount in charges(lines):
        low = desc.lower()
        proc = next((p for p in PROCEDURES if p in low), None)
        if proc and proc not in allowed:
            bad.append((0.85, f"{desc} billed for {dx} ({code}), which does not normally need it"))
        band = next((b for k, b in PER_DAY.items() if k in low), None)
        if band and days:
            rate = amount / days
            if not band[0] <= rate <= band[1]:
                bad.append((0.7, f"{desc} works out to {rate:,.0f} per day for a {days}-day stay "
                                 f"(expected {band[0]:,}–{band[1]:,}): more days billed than stayed?"))
    if days is not None and days > max_days:
        bad.append((0.6, f"a {days}-day stay for {dx} ({code}) is longer than the usual "
                         f"{max_days} days or less"))
    return code, dx, bad


def run(text: str, doc_type: str) -> Signal:
    res = check(text) if doc_type == "medical" else None
    if res is None:
        return Signal(NAME, None, 0.0, "Not applicable: no medical bill with a diagnosis in the "
                      "billing reference table.", applicable=False, tier="doc")
    code, dx, bad = res
    if not bad:
        return Signal(NAME, 0.1, 0.6, f"Charges and stay length fit the diagnosis ({dx}, {code}).",
                      {"icd10": code}, tier="doc")
    score, first = max(bad)
    more = f" ({len(bad) - 1} more issue(s))" if len(bad) > 1 else ""
    return Signal(NAME, score, 0.7, first[0].upper() + first[1:] + "." + more,
                  {"icd10": code, "issues": [b for _, b in bad]}, tier="doc")
