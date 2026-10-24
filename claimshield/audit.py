"""Reviewer audit trail: SQLite, one row per reviewer action. Stores SHA-256 hashes of the
evidence files and the scores — never the files themselves (README)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from . import config

DB = config.ROOT / "data" / "audit.sqlite"
SCHEMA = """CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY, case_id TEXT, sha256 TEXT, scores TEXT, band TEXT,
    reviewer TEXT, action TEXT, note TEXT, ts TEXT)"""
ACTIONS = ("accept", "reject", "escalate")


def _db(path=None):
    path = path or DB
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    return con


def record(case_id: str, hashes: list[str], claim, reviewer: str, action: str, note: str = "",
           path=None) -> None:
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    scores = {"overall": claim.overall, "image": claim.image_score,
              "document": claim.document_score, "identity": claim.identity_score,
              "waterfall": claim.waterfall}
    with closing(_db(path)) as con, con:
        con.execute("INSERT INTO audit (case_id, sha256, scores, band, reviewer, action, note, ts)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (case_id, ",".join(hashes), json.dumps(scores), claim.band, reviewer, action,
                     note, datetime.now(timezone.utc).isoformat(timespec="seconds")))


def history(case_id: str, path=None) -> list[dict]:
    with closing(_db(path)) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(
            "SELECT reviewer, action, note, band, ts FROM audit WHERE case_id = ? ORDER BY id",
            (case_id,))]
