"""HTTP API (claimshield/api.py) over a fake pipeline: routes, SSE order, JSON shapes, PNGs,
decisions → audit, arena, reports. No model weights, no cv2."""
import importlib
import io
import json
import sys
import threading
import types
from dataclasses import dataclass, replace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from claimshield import audit, cases  # noqa: E402
from claimshield.arena import attacks  # noqa: E402
from claimshield.contracts import ClaimScore, Signal  # noqa: E402

GATE = threading.Event()


@dataclass
class FakeImage:
    claim: ClaimScore
    sha256: str
    quality_reasons: list
    t_first: float
    t_fast: float
    t_deep: float | None = None
    deep: object = None
    quality_flag: bool = False
    rgb: object = None


@dataclass
class FakeDoc:
    claim: ClaimScore
    sha256: str
    doc_type: str
    text: str
    from_ocr: bool
    page: object
    t_total: float


def claim(signals, overall=0.7, band="HIGH", pending=False):
    return ClaimScore(overall, None, None, overall, band, [("baseline", 0.0), ("localizer", overall)],
                      [], signals, pending_deep=pending)


def fake_pipeline():
    m = types.ModuleType("claimshield.pipeline")

    def score_image(path, on_card=None, wait_deep=False):
        GATE.wait(5)
        rgb = Image.open(path).convert("RGB")
        sigs = [Signal("exif", 0.2, 0.4, "Camera metadata looks normal.", {"make": "X"}),
                Signal("localizer", 0.8, 0.7, "Edited area found.",
                       {"heatmap": np.full((rgb.height, rgb.width), 0.5), "integrity": 0.8})]
        for s in sigs:
            on_card and on_card(s)
        return FakeImage(claim(sigs, pending=True), "ab" * 32, [], 0.1, 0.2, rgb=rgb, deep=object())

    def finish(r):
        ae = Signal("ae_reconstruction", 0.6, 0.7, "Low error.",
                    {"patch_map": np.zeros((r.rgb.height, r.rgb.width))}, tier="deep")
        return replace(r, claim=claim(r.claim.signals + [ae]), t_deep=1.0, deep=None)

    def score_document(path, on_card=None):
        s = Signal("pdf_incremental_update", 0.9, 0.9, "Saved twice; total changed.",
                   {"diff": [("Total 100", "Total 900")]}, tier="doc")
        on_card and on_card(s)
        return FakeDoc(claim([s]), "cd" * 32, "invoice", "Total 900", False, None, 0.3)

    def score_identity(id_path, selfie_path, on_card=None):
        s = Signal("face_match", 0.9, 0.8, "Different people.", {"cosine": 0.1}, tier="identity")
        on_card and on_card(s)
        return [s], ""

    def combine(images, documents, identity, id_text="", on_card=None, case_id=None, remember=False,
                story=None):
        chk = Signal("name_mismatch", None, 0.0, "Not applicable.", applicable=False, tier="claim")
        on_card and on_card(chk)
        sigs = [s for r in (*images, *documents) for s in r.claim.signals] + identity + [chk]
        return types.SimpleNamespace(claim=claim(sigs, pending=any(r.deep for r in images)),
                                     narrative="Score [CLAIMANT_1] 0.70.", pii={"[CLAIMANT_1]": "Asha"})

    m.score_image, m.finish, m.score_document = score_image, finish, score_document
    m.score_identity, m.combine = score_identity, combine
    m.warm = lambda: ["clip_probe: missing models/heads/clip_probe.pkl"]
    return m


def jpg(path, size=(64, 48)):
    Image.new("RGB", size, (120, 80, 40)).save(path)


@pytest.fixture
def api(tmp_path, monkeypatch):
    import claimshield
    fake = fake_pipeline()
    monkeypatch.setitem(sys.modules, "claimshield.pipeline", fake)
    monkeypatch.setattr(claimshield, "pipeline", fake, raising=False)
    monkeypatch.delitem(sys.modules, "claimshield.api", raising=False)
    monkeypatch.setenv("CLAIMSHIELD_LLM_PRIMARY", "template")
    monkeypatch.delenv("SUPABASE_URL", raising=False)   # hermetic: login off, whatever .env says
    mod = importlib.import_module("claimshield.api")
    case = tmp_path / "cases" / "b_fraud"
    case.mkdir(parents=True)
    jpg(case / "front.jpg")
    jpg(case / "id.jpg")
    jpg(case / "selfie.jpg")
    (case / "invoice.pdf").write_bytes(b"%PDF-1.4 fake")
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    jpg(seeds / "car_0001.jpg")
    monkeypatch.setattr(cases, "CASES", tmp_path / "cases")
    monkeypatch.setattr(cases, "BANDS", tmp_path / "bands.json")
    monkeypatch.setattr(audit, "DB", tmp_path / "audit.sqlite")
    monkeypatch.setattr(mod, "SEEDS", seeds)
    monkeypatch.setattr(mod, "REPORTS", tmp_path / "reports")
    GATE.set()
    with TestClient(mod.app) as c:
        yield c, mod
    GATE.set()


def events(c, job_id):
    with c.stream("GET", f"/api/jobs/{job_id}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        text = "".join(r.iter_text())
    out = []
    for block in text.split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines() if not l.startswith(":") and ": " in l)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health_config_inbox(api):
    c, _ = api
    h = c.get("/api/health").json()
    assert h["ok"] is False and "clip_probe" in h["problems"][0]
    assert c.get("/api/config").json()["bands"] == {"low_max": 0.35, "medium_max": 0.65}
    [row] = c.get("/api/cases").json()
    assert row["case_id"] == "b_fraud" and row["counts"] == {"photos": 1, "documents": 1,
                                                             "id": True, "selfie": True}
    assert row["last_band"] is None


def test_score_case_streams_in_order_then_result_and_pictures(api):
    c, _ = api
    GATE.clear()
    r = c.post("/api/cases/b_fraud/score")
    assert r.status_code == 202
    job = r.json()["job_id"]
    assert c.get("/api/cases/b_fraud").status_code == 409          # still scoring
    GATE.set()
    ev = events(c, job)
    names = [e for e, _ in ev]
    assert names[0] == "card" and names[-1] == "final"
    order = [n for n in names if n != "card"]
    assert order == ["image_fast_done", "document_done", "provisional", "deep_done", "final"]
    lanes = {d["lane"] for e, d in ev if e == "card"}
    assert lanes == {"image", "document", "identity", "claim"}

    res = c.get("/api/cases/b_fraud").json()
    assert res["claim"]["band"] == "HIGH" and res["narrative"]["text"] == "Score Asha 0.70."
    assert res["narrative"]["source"] == "template"
    loc = next(s for s in res["images"][0]["claim"]["signals"] if s["name"] == "localizer")
    assert "heatmap" not in loc["evidence"] and loc["evidence"]["integrity"] == 0.8  # arrays dropped
    assert res["documents"][0]["claim"]["signals"][0]["evidence"]["diff"] == [["Total 100", "Total 900"]]
    urls = res["images"][0]["urls"]
    for u in (urls["photo"], urls["heatmap"], urls["reconstruction"], res["identity"]["urls"]["id"]):
        p = c.get(u)
        assert p.status_code == 200 and p.headers["content-type"] == "image/png"
        assert Image.open(io.BytesIO(p.content)).size == (64, 48)
    assert c.get("/api/cases/b_fraud/documents/0/page.png").status_code == 404   # no page image
    assert c.get("/api/cases").json()[0]["last_band"] == "HIGH"
    assert c.get("/api/cases/nope").json()["error"]["code"] == "not_found"


def test_decision_goes_to_audit(api):
    c, _ = api
    events(c, c.post("/api/cases/b_fraud/score").json()["job_id"])
    bad = c.post("/api/cases/b_fraud/decision", json={"action": "approve"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "bad_request"
    r = c.post("/api/cases/b_fraud/decision", json={"action": "reject", "note": "edited"},
               headers={"X-Reviewer": "asha"})
    assert r.status_code == 201 and r.json()["reviewer"] == "asha" and r.json()["band"] == "HIGH"
    c.post("/api/cases/b_fraud/decision", json={"action": "escalate", "reviewer": "ravi"})
    assert [h["reviewer"] for h in c.get("/api/cases/b_fraud/history").json()] == ["asha", "ravi"]


def test_arena_before_attack_after(api, monkeypatch):
    c, _ = api
    assert c.get("/api/arena/seeds").json()[0]["name"] == "car_0001.jpg"
    r = c.post("/api/arena", json={"seed": "car_0001.jpg"})
    assert r.status_code == 202
    aid = r.json()["arena_id"]
    assert events(c, r.json()["job_id"])[-1][0] == "final"
    assert c.post(f"/api/arena/{aid}/attack", json={"kind": "nope"}).status_code == 400

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 10, 10)).save(buf, "JPEG")
    monkeypatch.setitem(attacks.ATTACKS, "recompress_q70", lambda p: attacks.Attack(
        buf.getvalue(), "recompress_q70", "recompress", "Re-saved at JPEG quality 70.", 0.1))
    ev = events(c, c.post(f"/api/arena/{aid}/attack", json={"kind": "recompress_q70"}).json()["job_id"])
    assert [e for e, _ in ev if e != "card"] == ["attack", "final"]
    got = c.get(f"/api/arena/{aid}").json()
    assert got["before"] and got["after"] and got["attack"]["method"] == "recompress"
    assert c.get(f"/api/arena/{aid}/after/heatmap.png").headers["content-type"] == "image/png"

    def dead(p, prompt=None):
        raise RuntimeError("no attack path available")
    monkeypatch.setattr(attacks, "inpaint", dead)
    ev = events(c, c.post(f"/api/arena/{aid}/attack", json={"kind": "inpaint"}).json()["job_id"])
    assert ev[-1] == ("error", {"code": "attack_unavailable", "message": "no attack path available"})


def test_reports_404_then_served(api):
    c, mod = api
    assert c.get("/api/reports/heldout").status_code == 404
    mod.REPORTS.mkdir()
    (mod.REPORTS / "heldout_table.json").write_text('{"families": {}, "robustness": {}}')
    (mod.REPORTS / "eval_latest.md").write_text("# eval")
    assert c.get("/api/reports/heldout").json() == {"families": {}, "robustness": {}}
    assert c.get("/api/reports/eval").text == "# eval"


def test_upload_scores_then_wipes_temp_dir(api, monkeypatch):
    pytest.importorskip("python_multipart")
    c, mod = api
    made = []
    real = mod.tempfile.mkdtemp
    monkeypatch.setattr(mod.tempfile, "mkdtemp", lambda **kw: made.append(real(**kw)) or made[-1])
    buf = io.BytesIO()
    Image.new("RGB", (64, 48)).save(buf, "JPEG")
    r = c.post("/api/cases", files={"photos": ("p.jpg", buf.getvalue(), "image/jpeg")},
               data={"title": "Upload"})
    assert r.status_code == 202 and r.json()["case_id"].startswith("upload-")
    assert events(c, r.json()["job_id"])[-1][0] == "final"
    assert c.get(f"/api/cases/{r.json()['case_id']}").json()["title"] == "Upload"
    import os
    assert made and not os.path.exists(made[0])
    bad = c.post("/api/cases", files={"photos": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415
