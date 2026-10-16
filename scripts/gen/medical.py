"""Medical-report (discharge summary) PDFs → data/docs/clean/medical_<n>.pdf + .json, and with
--upcoded N also data/docs/upcoded/medical_<kind>_<n>.pdf (health-insurance billing fraud).
Same writer and sidecar format as invoices.py.

Clean reports bill only care that fits the diagnosis (claimshield/signals/documents/
medical_billing.CARE), a normal stay, and normal daily rates. Upcoded ones break exactly one
rule: "procedure" (a procedure the diagnosis doesn't need), "stay" (stay too long for the
diagnosis), "days" (room/nursing billed for more days than the stay).
Usage: python scripts/gen/medical.py [--n 50] [--upcoded 30]
"""
import argparse
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import invoices  # noqa: E402
from invoices import NAMES, Page, money, save  # noqa: E402

from claimshield.signals.documents.medical_billing import CARE  # noqa: E402

HOSPITALS = [("St. Anne's Multispeciality Hospital", ("F1", "F2"), "%d/%m/%Y", "Microsoft Word 2016"),
             ("Riverside Trauma & Ortho Centre", ("F3", "F4"), "%Y-%m-%d", "HIS Report Server 4.2"),
             ("Lotus Medical Institute", ("F1", "F2"), "%d %b %Y", "Crystal Reports")]
DIAGNOSES = [("S82.0", "Fracture of patella"), ("S52.5", "Fracture of lower end of radius"),
             ("S06.0", "Concussion"), ("S13.4", "Sprain of ligaments of cervical spine"),
             ("S43.0", "Dislocation of shoulder joint"), ("S22.3", "Fracture of rib"),
             ("S83.5", "Sprain of cruciate ligament of knee")]
BASICS = [("Room charges (per day)", 4500), ("Nursing (per day)", 1800), ("Consultation", 1500),
          ("Pharmacy", 3800)]
PROCEDURE_CHARGES = {"x-ray": ("X-ray", 1200), "ct scan": ("CT scan", 6500),
                     "surgery": ("Surgery", 45000), "physiotherapy": ("Physiotherapy session", 900)}
UPCODES = ("procedure", "stay", "days")


def report(i, rng, upcode=None, hospital=None, patient=None, admitted=None):
    name, (reg, bold), datefmt, producer = (rng.choice(HOSPITALS) if hospital is None
                                            else HOSPITALS[hospital])
    pool = ([d for d in DIAGNOSES if set(PROCEDURE_CHARGES) - CARE[d[0]][1]] if upcode == "procedure"
            else DIAGNOSES)   # a diagnosis that allows every procedure can't be upcoded by one
    code, dx = rng.choice(pool)
    _, allowed, max_days = CARE[code]
    days = rng.randint(max_days + 2, max_days + 5) if upcode == "stay" else rng.randint(1, max_days)
    adm = dt.date(2026, 1, 1) + dt.timedelta(days=rng.randrange(0, 230))
    adm = admitted or adm   # demo cases pin the stay (scripts/gen/health_cases.py)
    dis = adm + dt.timedelta(days=days)

    procs = rng.sample(sorted(allowed), rng.randint(1, len(allowed)))
    if upcode == "procedure":
        procs.append(rng.choice(sorted(set(PROCEDURE_CHARGES) - allowed)))
    items = rng.sample(BASICS, rng.randint(2, len(BASICS))) + [PROCEDURE_CHARGES[p] for p in procs]
    if upcode == "days" and not any("per day" in d for d, _ in items):
        items.append(BASICS[0])
    billed_days = days * 3 if upcode == "days" else days   # ≥ 3× the stay: daily rate leaves the band

    p, L = Page(), 50
    p.text(L, 780, 16, bold, name, "hospital")
    p.text(L, 760, 12, bold, "DISCHARGE SUMMARY")
    p.text(L, 730, 10, reg, "Patient: " + (patient or rng.choice(NAMES)), "patient")
    p.text(L, 716, 10, reg, f"Age: {rng.randint(18, 80)}    UHID: {rng.randrange(10**7, 10**8)}", "uhid")
    p.text(L, 702, 10, reg, "Admitted: " + adm.strftime(datefmt), "admission_date")
    p.text(L, 688, 10, reg, "Discharged: " + dis.strftime(datefmt), "discharge_date")
    p.text(L, 660, 10, bold, "Diagnosis")
    p.text(L, 646, 10, reg, f"{dx} (ICD-10 {code})", "diagnosis")
    p.text(L, 618, 10, bold, "Charges")
    p.line(L, 612, 545, 612)
    y, total = 612, 0
    for k, (desc, unit) in enumerate(items):
        amt = round(unit * rng.uniform(0.8, 1.3), -1)
        if "per day" in desc:
            amt *= billed_days
        y -= 18
        p.text(L, y, 10, reg, desc, f"item{k}_desc")
        p.text(450, y, 10, reg, money(amt), f"item{k}_amount")
        total += amt
    p.line(L, y - 8, 545, y - 8)
    p.text(330, y - 26, 10, bold, "Total (INR)")
    p.text(450, y - 26, 10, bold, money(total), "total")
    p.text(L, 100, 9, reg, "Attending physician: Dr. " + rng.choice(NAMES).split()[1])
    created = dt.datetime.combine(dis, dt.time(rng.randrange(10, 20), rng.randrange(60)))
    return p, producer, created, {"icd10": code, "upcode": upcode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--upcoded", type=int, default=0, help="this many of EACH upcode kind")
    a = ap.parse_args()
    for i in range(a.n):
        save(f"medical_{i:04d}", *report(i, random.Random(f"medical/{i}")))
    print(f"wrote {a.n} medical reports to {invoices.OUT}")
    if a.upcoded:
        invoices.OUT = invoices.OUT.parent / "upcoded"
        for kind in UPCODES:
            for i in range(a.upcoded):
                save(f"medical_{kind}_{i:04d}", *report(i, random.Random(f"medical/{kind}/{i}"), kind))
        print(f"wrote {3 * a.upcoded} upcoded reports to {invoices.OUT}")


if __name__ == "__main__":
    main()
