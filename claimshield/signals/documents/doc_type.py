"""D2: document type by keyword rules → invoice | medical | id | other."""
from __future__ import annotations

KEYWORDS = {
    "invoice": ("invoice", "bill to", "subtotal", "gst", "gstin", "amount due", "tax invoice",
                "unit price", "qty"),
    "medical": ("discharge", "diagnosis", "icd", "patient", "hospital", "admitted",
                "physician", "uhid", "prescription"),
    "id": ("passport", "date of birth", "nationality", "driving licence", "driving license",
           "identity card", "place of birth", "<<<"),
}


def classify(text: str) -> str:
    # ponytail: keyword counts only; ties/zero → "other". LLM-to-JSON for ambiguous docs
    # (ARCHITECTURE D2) waits for the Phase 7 LLM client.
    low = text.lower()
    hits = {t: sum(k in low for k in ks) for t, ks in KEYWORDS.items()}
    best = max(hits, key=hits.get)
    ranked = sorted(hits.values(), reverse=True)
    return best if ranked[0] >= 2 and ranked[0] > ranked[1] else "other"
