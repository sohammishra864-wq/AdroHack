"""Template narrative: instant, deterministic, built only from the score, the waterfall and
each signal's reason. PII is replaced by placeholders ([NAME_1], [ID_1], …) BEFORE the text
leaves this module; fill() puts the real values back locally for the reviewer.
"""
from __future__ import annotations

import re

from ..contracts import ClaimScore

BAND_TEXT = {"LOW": "low risk", "MEDIUM": "medium risk — review recommended",
             "HIGH": "high risk — escalate", "UNCERTAIN": "uncertain — the evidence is too weak "
             "or too degraded to call"}
PII = [("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
       ("MRZ", re.compile(r"[A-Z0-9<]{30,44}")),
       ("PHONE", re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?\d{5}[ -]?\d{5}(?!\d)")),
       ("ID", re.compile(r"(?<![\d,.])\d{6,}(?!\d|[.,]\d)"))]  # long digit runs: UHID, Aadhaar…


def scrub(text: str, names: list[str] = (), mapping: dict | None = None) -> tuple[str, dict]:
    """Replace names and PII patterns with stable placeholders. mapping: placeholder → value."""
    mapping = {} if mapping is None else mapping
    back = {v: k for k, v in mapping.items()}

    def ph(kind, value):
        if value not in back:
            back[value] = f"[{kind}_{sum(k.startswith(f'[{kind}_') for k in mapping) + 1}]"
            mapping[back[value]] = value
        return back[value]

    for n in sorted({n for n in names if n}, key=len, reverse=True):
        text = re.sub(re.escape(n), lambda m: ph("NAME", n), text, flags=re.I)
    for kind, rx in PII:
        text = rx.sub(lambda m: ph(kind, m.group(0)), text)
    return text, mapping


def fill(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def build(claim: ClaimScore, names: list[str] = ()) -> tuple[str, dict]:
    """→ (placeholder text, mapping). Show fill(text, mapping) to the reviewer."""
    reason = {s.name: s.reason for s in claim.signals if s.score is not None}
    contrib = [(k, v) for k, v in claim.waterfall if k != "baseline" and k in reason]
    up = [k for k, v in contrib if v > 0][:3]
    down = [k for k, v in contrib if v < 0][:2]

    parts = [f"Overall: {claim.band} ({claim.overall:.2f}), {BAND_TEXT[claim.band]}."]
    if up:
        parts.append("Main concerns: " + " ".join(f"({i}) {reason[k]}" for i, k in
                                                   enumerate(up, 1)))
    if down:
        parts.append("Pointing the other way: " + " ".join(reason[k] for k in down))
    parts += [r.reason for r in claim.regions[:3]]
    skipped = [s.name for s in claim.signals if s.score is None and s.applicable]
    if skipped:
        parts.append(f"Left out of the score: {', '.join(skipped)}.")
    if claim.pending_deep:
        parts.append("The reconstruction test is still running; the score may change.")
    return scrub("\n".join(parts), names)
