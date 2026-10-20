"""Cross-claim memory: links across cases, pHash tolerance, window, no clear text stored."""
import sqlite3
from datetime import datetime, timedelta, timezone

from claimshield import memory

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
PH = "f0e1d2c3b4a59687"


def flip(h: str, bits: int) -> str:
    return f"{int(h, 16) ^ ((1 << bits) - 1):016x}"


def test_links_photo_copy_and_same_shop(tmp_path):
    db = tmp_path / "m.sqlite"
    memory.remember("case-a", {"photo": [PH], "vendor": ["Shree Auto Works"],
                               "vin": ["MA3EYD32S00123456"]}, path=db, now=T0)
    got = memory.links("case-b", {"photo": [flip(PH, 3)], "vendor": ["SHREE AUTO WORKS."],
                                  "vin": ["ma3 eyd32s00123456"]}, path=db, now=T0)
    assert sorted(l["kind"] for l in got) == ["photo", "vendor", "vin"]
    assert {l["case_id"] for l in got} == {"case-a"}


def test_no_link_for_different_photo_own_case_or_old_rows(tmp_path):
    db = tmp_path / "m.sqlite"
    memory.remember("case-a", {"photo": [PH]}, path=db, now=T0 - timedelta(days=400))
    memory.remember("case-c", {"photo": [PH]}, path=db, now=T0)
    assert memory.links("case-b", {"photo": [flip(PH, memory.PHASH_MAX_DIST + 1)]}, path=db, now=T0) == []
    assert memory.links("case-c", {"photo": [PH]}, path=db, now=T0) == []          # itself
    assert [l["case_id"] for l in memory.links("case-b", {"photo": [PH]}, path=db, now=T0)] == ["case-c"]


def test_reset_clears_memory_but_not_the_audit_trail(tmp_path):
    db = tmp_path / "m.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, case_id TEXT)")
    con.execute("INSERT INTO audit (case_id) VALUES ('r1_first')")
    con.commit()
    con.close()
    memory.remember("r1_first", {"vendor": ["Speedline Auto Repairs"]}, path=db, now=T0)
    assert memory.reset(path=db) == 1
    assert memory.links("x", {"vendor": ["Speedline Auto Repairs"]}, path=db, now=T0) == []
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1


def test_rescoring_replaces_rows_and_text_is_hashed(tmp_path):
    db = tmp_path / "m.sqlite"
    memory.remember("case-a", {"claimant": ["Asha Rao"]}, path=db, now=T0)
    memory.remember("case-a", {"claimant": ["Asha Rao"]}, path=db, now=T0)
    rows = sqlite3.connect(db).execute("SELECT value FROM claims_seen").fetchall()
    assert len(rows) == 1 and "asha" not in rows[0][0].lower()
