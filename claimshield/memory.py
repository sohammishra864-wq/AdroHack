"""Cross-claim memory: which evidence each scored claim used, so a later claim that reuses it
can be linked (same photo, VIN, repair shop or claimant). One row per (case, entity).
Text entities are stored as SHA-256 of the normalised value, never in clear (privacy
rule). Photos are stored as a 64-bit perceptual hash, which still matches resized or
recompressed copies."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from . import config

DB = config.ROOT / "data" / "audit.sqlite"   # same file as the audit trail, own table
SCHEMA = """CREATE TABLE IF NOT EXISTS claims_seen (
    case_id TEXT, kind TEXT, value TEXT, ts TEXT)"""
KINDS = ("photo", "vin", "vendor", "claimant", "stay")
# Hamming bits out of 64. Measured on 200 seeds: q30-q50 + resize copies ≤ 2, different photos
# ≥ 14 (0 of 19,900 pairs ≤ 10); a 5 % crop is caught 64 % of the time, a 10 % crop rarely.
PHASH_MAX_DIST = 10
WINDOW_DAYS = 180


def _db(path=None):
    path = path or DB
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    return con


def norm(kind: str, value: str) -> str:
    """Stored form: pHash hex as is; text → SHA-256 of the case/punctuation-folded value."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if kind == "photo":
        return value.lower()
    v = " ".join(re.sub(r"[^\w ]", " ", value).split()).casefold()
    if kind == "vin":
        v = v.replace(" ", "").upper()
    return hashlib.sha256(f"{kind}:{v}".encode()).hexdigest()


def _same(kind: str, a: str, b: str) -> bool:
    if kind == "photo":
        return bin(int(a, 16) ^ int(b, 16)).count("1") <= PHASH_MAX_DIST
    return a == b


def _now(now):
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def remember(case_id: str, entities: dict[str, list[str]], path=None, now=None) -> None:
    """Store this case's entities, replacing any earlier rows for the same case (rescoring)."""
    ts = _now(now)
    rows = [(case_id, k, norm(k, v), ts) for k, vs in entities.items() for v in set(vs) if v]
    with closing(_db(path)) as con, con:
        con.execute("DELETE FROM claims_seen WHERE case_id = ?", (case_id,))
        con.executemany("INSERT INTO claims_seen VALUES (?, ?, ?, ?)", rows)


def reset(path=None) -> int:
    """Forget every remembered claim (demo restart). Never touches the audit trail table."""
    with closing(_db(path)) as con, con:
        return con.execute("DELETE FROM claims_seen").rowcount


def links(case_id: str, entities: dict[str, list[str]], path=None, now=None,
          days: int = WINDOW_DAYS) -> list[dict]:
    """Other cases within the window that share an entity with this one. `value` is this
    claim's own clear-text value (for the card); stored rows never hold clear text."""
    since = _now((now or datetime.now(timezone.utc)) - timedelta(days=days))
    with closing(_db(path)) as con:
        # ponytail: linear scan over the window; add an index + pHash BK-tree past ~100k rows.
        seen = con.execute("SELECT case_id, kind, value, ts FROM claims_seen "
                           "WHERE case_id != ? AND ts >= ? ORDER BY ts", (case_id, since)).fetchall()
    out = []
    for kind, values in entities.items():
        for v in sorted({x for x in values if x}):
            h = norm(kind, v)
            out += [{"kind": kind, "value": v, "case_id": c, "ts": t}
                    for c, k, s, t in seen if k == kind and _same(kind, h, s)]
    return out
