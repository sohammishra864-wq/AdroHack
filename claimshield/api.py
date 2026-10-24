"""HTTP API over the pipeline for a JS/React frontend (README).

Thin layer: every route calls an existing function (pipeline, cases, audit, arena, narrative);
no scoring logic lives here. Long work runs as a job on a thread and streams Server-Sent
Events (`card`, `provisional`, `deep_done`, `final`, …), the HTTP form of Streamlit's on_card.
Results and pictures live in memory (like Streamlit session_state); uploads are written to a
temp dir that is deleted as soon as scoring ends.

Run:  uvicorn claimshield.api:app --port 8000     (make api)
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import Future
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from PIL import Image, ImageOps

from . import audit, cases, config, pipeline
from . import auth
from .arena import attacks
from .narrative import llm, template

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
DOC_EXT = IMAGE_EXT | {".pdf"}
PROBLEMS: list[str] = []
RESULTS: dict[str, dict] = {}   # case_id → {"json", "claim", "hashes", "images", "pages", "id_rgb", "selfie_rgb"}
JOBS: dict[str, "Job"] = {}
RUNNING: dict[str, "Job"] = {}  # case_id / arena_id → job still scoring
ARENA: dict[str, dict] = {}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@asynccontextmanager
async def lifespan(_app):
    PROBLEMS[:] = pipeline.warm()  # load every model once, before the first request
    yield


app = FastAPI(title="ClaimShield API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=os.environ.get("CLAIMSHIELD_CORS_ORIGINS",
                                                "http://localhost:5173").split(","))


@app.exception_handler(ApiError)
async def _api_error(_req, e: ApiError):
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:].strip() or None if h.lower().startswith("bearer ") else None


def current_user(request: Request) -> dict:
    """The one auth hook. A bearer token (Supabase on) must be valid → verified user. No token →
    whoever X-Reviewer names, unverified (demo personas; the demo is never blocked at login)."""
    token = _bearer(request)
    if token and auth.enabled():
        try:
            u = auth.user_from_token(token)
        except auth.AuthError as e:
            raise ApiError(e.status, "unauthorized" if e.status == 401 else "auth_unavailable", e.message)
        return {"user": u["full_name"] or u["email"], "verified": True, "role": u["role"], "email": u["email"]}
    return {"user": request.headers.get("x-reviewer"), "verified": False}


# ------------------------------------------------------------------------------ auth
def _auth_call(fn, *args):
    if not auth.enabled():
        raise ApiError(503, "auth_disabled", "Login is not configured (no SUPABASE_URL); use the demo personas.")
    try:
        return fn(*args)
    except auth.AuthError as e:
        raise ApiError(e.status, "auth_failed", e.message)


@app.get("/api/auth/status")
def auth_status():
    return {"enabled": auth.enabled()}


@app.post("/api/auth/signup")
async def auth_signup(request: Request):
    b = await request.json()
    return _auth_call(auth.sign_up, str(b.get("email", "")), str(b.get("password", "")),
                      str(b.get("full_name") or ""), b.get("organization"))


@app.post("/api/auth/login")
async def auth_login(request: Request):
    b = await request.json()
    return _auth_call(auth.sign_in, str(b.get("email", "")), str(b.get("password", "")))


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    token = _bearer(request)
    if token:
        _auth_call(auth.sign_out, token)
    return {"ok": True}


@app.get("/api/auth/user")
def auth_user(request: Request):
    u = current_user(request)
    if not u["verified"]:
        raise ApiError(401, "unauthorized", "Not logged in.")
    return u


# --------------------------------------------------------------------------- serialising
def _binary(v) -> bool:
    return isinstance(v, (np.ndarray, Image.Image, bytes, Future))


def _json(o):
    """Dataclasses / numpy / datetime → plain JSON. Arrays and images are dropped: the PNG
    endpoints serve them."""
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: _json(getattr(o, f.name)) for f in dataclasses.fields(o)
                if not _binary(getattr(o, f.name))}
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items() if not _binary(v)}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o if not _binary(v)]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if o is None or isinstance(o, (str, int, float, bool)):
        return o
    return str(o)


def _sig(claim, name):
    return next((s for s in claim.signals if s.name == name), None)


def _arr(sig, key):
    v = sig.evidence.get(key) if sig is not None else None
    return v if isinstance(v, np.ndarray) else None


def _image(i: int, name: str, r, base: str) -> dict:
    loc, ae = _sig(r.claim, "localizer"), _sig(r.claim, "ae_reconstruction")
    return {"index": i, "name": name, "sha256": r.sha256, "claim": _json(r.claim),
            "quality_flag": r.quality_flag, "quality_reasons": list(r.quality_reasons),
            "timing": {"first_card_s": r.t_first, "fast_tier_s": r.t_fast, "deep_s": r.t_deep},
            "urls": {"photo": f"{base}/photo.png",
                     "heatmap": f"{base}/heatmap.png" if _arr(loc, "heatmap") is not None else None,
                     "reconstruction": f"{base}/reconstruction.png"
                     if _arr(ae, "patch_map") is not None else None}}


def _doc(i: int, name: str, d, page, base: str) -> dict:
    return {"index": i, "name": name, "sha256": d.sha256, "doc_type": d.doc_type,
            "from_ocr": d.from_ocr, "text": d.text, "claim": _json(d.claim),
            "timing": {"total_s": d.t_total},
            "urls": {"page": f"{base}/page.png" if page is not None else None}}


def _png(x) -> Response:
    if x is None:
        raise ApiError(404, "not_found", "No such picture for this result.")
    img = Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8), "L") \
        if isinstance(x, np.ndarray) else x
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png")


def _rgb(path: str):
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def _page(path: str, d):
    if d.page is not None or not path.lower().endswith(".pdf"):
        return d.page
    try:  # a text-layer PDF still gets a picture (needs Poppler)
        from .signals.documents import ocr
        return ocr.render(Path(path).read_bytes())[0]
    except Exception:
        return None


# ------------------------------------------------------------------------------- jobs
class Job:
    """Events of one scoring run. The SSE stream replays them, so a late client misses nothing."""

    def __init__(self):
        self.id = "j_" + uuid.uuid4().hex[:12]
        self.events: list[tuple[str, object]] = []
        self.done = False
        self.cv = threading.Condition()
        JOBS[self.id] = self

    def emit(self, event: str, data) -> None:
        with self.cv:
            self.events.append((event, _json(data)))
            self.done = self.done or event in ("final", "error")
            self.cv.notify_all()

    def stream(self):
        i = 0
        while True:
            with self.cv:
                self.cv.wait_for(lambda: len(self.events) > i or self.done, timeout=15)
                new, done = self.events[i:], self.done
            i += len(new)
            for ev, data in new:
                yield f"event: {ev}\ndata: {json.dumps(data)}\n\n"
            if done and i >= len(self.events):
                return
            if not new:
                yield ": keep-alive\n\n"


def _start(key: str, target, *args) -> Job:
    job = Job()
    RUNNING[key] = job

    def run():
        try:
            target(job, *args)
        except ApiError as e:
            job.emit("error", {"code": e.code, "message": e.message})
        except Exception as e:  # the job dies, the server does not
            job.emit("error", {"code": "internal", "message": f"{type(e).__name__}: {e}"})
        finally:
            RUNNING.pop(key, None)

    threading.Thread(target=run, daemon=True).start()
    return job


def _accepted(key_name: str, key: str, job: Job) -> JSONResponse:
    return JSONResponse({key_name: key, "job_id": job.id, "events": f"/api/jobs/{job.id}/events"},
                        status_code=202)


def _score_case(job: Job, case, cleanup=None) -> None:
    """ui/app.py run_case without Streamlit: lanes → provisional → deep tier → final."""
    try:
        base = f"/api/cases/{case.id}"
        names = [Path(p).name for p in case.photos]
        doc_names = [Path(p).name for p in case.docs]

        def on(lane, i):
            return lambda s: job.emit("card", {"lane": lane, "index": i, "signal": s})

        images = []
        for i, p in enumerate(case.photos):
            images.append(pipeline.score_image(p, on_card=on("image", i)))
            job.emit("image_fast_done", {"index": i, "result": _image(i, names[i], images[i],
                                                                       f"{base}/images/{i}")})
        docs, pages = [], []
        for i, p in enumerate(case.docs):
            docs.append(pipeline.score_document(p, on_card=on("document", i)))
            pages.append(_page(p, docs[i]))
            job.emit("document_done", {"index": i, "result": _doc(i, doc_names[i], docs[i], pages[i],
                                                                   f"{base}/documents/{i}")})
        has_id = bool(case.id_path and case.selfie)
        identity, id_text = (pipeline.score_identity(case.id_path, case.selfie, on_card=on("identity", 0))
                             if has_id else ([], ""))
        job.emit("provisional", {"claim": pipeline.combine(images, docs, identity, id_text,
                                                           case_id=case.id, story=case.description).claim})
        for i, r in enumerate(images):
            images[i] = pipeline.finish(r)
            job.emit("deep_done", {"index": i, "signal": _sig(images[i].claim, "ae_reconstruction"),
                                   "result": _image(i, names[i], images[i], f"{base}/images/{i}")})
        res = pipeline.combine(images, docs, identity, id_text, on_card=on("claim", 0),
                               case_id=case.id, remember=True, story=case.description)
        out = llm.result(llm.start(res.narrative))  # only placeholder text leaves the process
        body = {"case_id": case.id, "title": case.title, "status": "done", "claim": _json(res.claim),
                "images": [_image(i, n, r, f"{base}/images/{i}") for i, (n, r) in enumerate(zip(names, images))],
                "documents": [_doc(i, n, d, pg, f"{base}/documents/{i}")
                              for i, (n, d, pg) in enumerate(zip(doc_names, docs, pages))],
                "identity": {"signals": _json(identity),
                             "urls": {"id": f"{base}/identity/id.png",
                                      "selfie": f"{base}/identity/selfie.png"}} if has_id else None,
                "narrative": {"text": template.fill(out or res.narrative, res.pii),
                              "source": "llm" if out else "template"},
                "hashes": cases.hashes(case)}
        RESULTS[case.id] = {"json": body, "claim": res.claim, "hashes": body["hashes"],
                            "images": images, "pages": pages,
                            "id_rgb": _rgb(case.id_path) if has_id else None,
                            "selfie_rgb": _rgb(case.selfie) if has_id else None}
        cases.save_band(case.id, res.claim.band)
        job.emit("final", body)
    finally:
        if cleanup:
            cleanup()


# ------------------------------------------------------------------------------- meta
@app.get("/api/health")
def health():
    return {"ok": not PROBLEMS, "problems": PROBLEMS, "device": config.device()}


@app.get("/api/config")
def get_config():
    return {"bands": config.cfg("thresholds")["bands"], "weights": config.cfg("weights"),
            "arena_attacks": list(attacks.ATTACKS), "arena_default_prompt": attacks._cfg()["prompt"],
            "accepted_types": {"image": sorted(e[1:] for e in IMAGE_EXT),
                               "document": sorted(e[1:] for e in DOC_EXT)}}


# ------------------------------------------------------------------------------ cases
@app.get("/api/cases")
def list_cases():
    bands = cases.last_bands()
    return [{"case_id": c.id, "title": c.title,
             "counts": {"photos": len(c.photos), "documents": len(c.docs),
                        "id": c.id_path is not None, "selfie": c.selfie is not None},
             "last_band": bands.get(c.id)} for c in cases.inbox()]


def _inbox_case(case_id: str):
    c = next((c for c in cases.inbox() if c.id == case_id), None)
    if c is None:
        raise ApiError(404, "not_found", f"No case '{case_id}' in the inbox.")
    return c


@app.post("/api/cases/{case_id}/score", status_code=202)
def score_inbox_case(case_id: str):
    if case_id in RUNNING:   # already scoring (inbox case or upload): follow that job, never run it twice
        return _accepted("case_id", case_id, RUNNING[case_id])
    case = _inbox_case(case_id)
    RESULTS.pop(case_id, None)
    return _accepted("case_id", case_id, _start(case_id, _score_case, case))


def _ext(name: str | None) -> str:
    return Path(name or "").suffix.lower()


@app.post("/api/cases", status_code=202)
async def upload_case(request: Request):
    """multipart: photos[], documents[], id, selfie, title, description. Parsed by hand (request.form()) so
    python-multipart is needed only when an upload actually arrives."""
    form = await request.form()
    files = []
    for field, prefix, allowed in (("photos", "photo", IMAGE_EXT), ("documents", "doc", DOC_EXT)):
        for i, f in enumerate(x for x in form.getlist(field) if getattr(x, "filename", None)):
            if _ext(f.filename) not in allowed:
                raise ApiError(415, "unsupported_file", f"{f.filename}: unsupported file type.")
            files.append((f"{prefix}_{i}{_ext(f.filename)}", await f.read()))
    for role in ("id", "selfie"):
        f = form.get(role)
        if getattr(f, "filename", None):
            if _ext(f.filename) not in IMAGE_EXT:
                raise ApiError(415, "unsupported_file", f"{f.filename}: unsupported file type.")
            files.append((f"{role}{_ext(f.filename)}", await f.read()))
    if not any(n.startswith(("photo_", "doc_")) for n, _ in files):
        raise ApiError(400, "bad_request", "Upload at least one photo or document.")
    case_id = "upload-" + hashlib.sha256(b"".join(d for _, d in files)).hexdigest()[:8]
    d = tempfile.mkdtemp(prefix="claimshield-")
    for n, data in files:
        Path(d, n).write_bytes(data)
    case = cases.load(Path(d), case_id)
    case.title = str(form.get("title") or case_id)
    case.description = str(form.get("description") or "")
    RESULTS.pop(case_id, None)
    job = _start(case_id, _score_case, case, lambda: shutil.rmtree(d, ignore_errors=True))
    return _accepted("case_id", case_id, job)


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise ApiError(404, "not_found", f"No job '{job_id}'.")
    return StreamingResponse(job.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _result(case_id: str) -> dict:
    if case_id in RESULTS:
        return RESULTS[case_id]
    if case_id in RUNNING:
        raise ApiError(409, "not_ready", "Still scoring; follow the job's events.")
    raise ApiError(404, "not_found", f"Case '{case_id}' has not been scored.")


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return _result(case_id)["json"]


def _nth(items: list, i: int):
    if not 0 <= i < len(items):
        raise ApiError(404, "not_found", "No such item in this result.")
    return items[i]


@app.get("/api/cases/{case_id}/images/{i}/{kind}.png")
def image_png(case_id: str, i: int, kind: str):
    r = _nth(_result(case_id)["images"], i)
    if kind == "photo":
        return _png(r.rgb)
    if kind == "heatmap":
        return _png(_arr(_sig(r.claim, "localizer"), "heatmap"))
    if kind == "reconstruction":
        return _png(_arr(_sig(r.claim, "ae_reconstruction"), "patch_map"))
    raise ApiError(404, "not_found", f"No picture '{kind}'.")


@app.get("/api/cases/{case_id}/documents/{i}/page.png")
def page_png(case_id: str, i: int):
    return _png(_nth(_result(case_id)["pages"], i))


@app.get("/api/cases/{case_id}/identity/{role}.png")
def identity_png(case_id: str, role: str):
    if role not in ("id", "selfie"):
        raise ApiError(404, "not_found", f"No picture '{role}'.")
    return _png(_result(case_id)[f"{role}_rgb"])


@app.post("/api/cases/{case_id}/decision", status_code=201)
async def decision(case_id: str, request: Request):
    body = await request.json()
    action = body.get("action")
    if action not in audit.ACTIONS:
        raise ApiError(400, "bad_request", f"action must be one of {list(audit.ACTIONS)}.")
    r = _result(case_id)
    who = current_user(request)
    reviewer = who["user"] or body.get("reviewer") or "reviewer"
    if auth.enabled() and not who["verified"]:
        reviewer += " (demo)"   # login is on but this decision came from a demo persona
    audit.record(case_id, r["hashes"], r["claim"], reviewer, action, body.get("note", ""))
    return {"case_id": case_id, **audit.history(case_id)[-1]}


@app.get("/api/cases/{case_id}/history")
def history(case_id: str):
    return audit.history(case_id)


# ------------------------------------------------------------------------------ arena
SEEDS = config.ROOT / "data" / "seeds"


def _seeds() -> list[Path]:
    return sorted(p for p in SEEDS.glob("*") if p.suffix.lower() in IMAGE_EXT)[:50] \
        if SEEDS.exists() else []


@app.get("/api/arena/seeds")
def arena_seeds():
    return [{"name": p.name, "url": f"/api/arena/seeds/{p.name}"} for p in _seeds()]


@app.get("/api/arena/seeds/{name}")
def arena_seed(name: str):
    p = next((p for p in _seeds() if p.name == name), None)
    if p is None:
        raise ApiError(404, "not_found", f"No seed '{name}'.")
    return Response(p.read_bytes(), media_type="image/png" if p.suffix.lower() == ".png" else "image/jpeg")


def _score_photo(job: Job, data: bytes, suffix: str, on_card):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"photo{suffix}"
        p.write_bytes(data)
        return pipeline.finish(pipeline.score_image(str(p), on_card=on_card))


def _card(job: Job):
    return lambda s: job.emit("card", {"lane": "image", "index": 0, "signal": s})


def _arena_before(job: Job, aid: str) -> None:
    A = ARENA[aid]
    A["before"] = _score_photo(job, A["data"], A["suffix"], _card(job))
    job.emit("final", {"before": _image(0, A["name"], A["before"], f"/api/arena/{aid}/before")})


@app.post("/api/arena", status_code=202)
async def arena_score(request: Request):
    # JSON {"seed": name} needs no python-multipart; a photo upload is multipart
    if request.headers.get("content-type", "").startswith("application/json"):
        f, seed = None, (await request.json()).get("seed")
    else:
        form = await request.form()
        f, seed = form.get("photo"), form.get("seed")
    if getattr(f, "filename", None):
        if _ext(f.filename) not in IMAGE_EXT:
            raise ApiError(415, "unsupported_file", f"{f.filename}: unsupported file type.")
        data, name = await f.read(), f.filename
    elif seed:
        p = next((p for p in _seeds() if p.name == seed), None)
        if p is None:
            raise ApiError(404, "not_found", f"No seed '{seed}'.")
        data, name = p.read_bytes(), p.name
    else:
        raise ApiError(400, "bad_request", "Send a photo file or a seed name.")
    aid = "a_" + uuid.uuid4().hex[:12]
    ARENA[aid] = {"data": data, "name": name, "suffix": _ext(name), "before": None,
                  "after": None, "attack": None}
    return _accepted("arena_id", aid, _start(aid, _arena_before, aid))


def _arena_after(job: Job, aid: str, kind: str, prompt: str | None) -> None:
    A = ARENA[aid]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"photo{A['suffix']}"
        p.write_bytes(A["data"])
        try:
            atk = attacks.inpaint(p, prompt) if kind == "inpaint" else attacks.ATTACKS[kind](p)
        except RuntimeError as e:
            raise ApiError(503, "attack_unavailable", str(e))
    info = {"kind": kind, "method": atk.method, "note": atk.note, "seconds": atk.seconds}
    job.emit("attack", info)
    A["after"] = _score_photo(job, atk.data, ".jpg", _card(job))
    A["attack"] = info
    job.emit("final", {"after": _image(0, A["name"], A["after"], f"/api/arena/{aid}/after"),
                       "attack": info})


def _arena(aid: str) -> dict:
    if aid not in ARENA:
        raise ApiError(404, "not_found", f"No arena run '{aid}'.")
    return ARENA[aid]


@app.post("/api/arena/{aid}/attack", status_code=202)
async def arena_attack(aid: str, request: Request):
    A = _arena(aid)
    if A["before"] is None:
        raise ApiError(409, "not_ready", "Score the original photo first.")
    body = await request.json()
    kind = body.get("kind")
    if kind not in attacks.ATTACKS:
        raise ApiError(400, "bad_request", f"kind must be one of {list(attacks.ATTACKS)}.")
    prompt = body.get("prompt") or attacks._cfg()["prompt"] if kind == "inpaint" else None
    return _accepted("arena_id", aid, _start(aid, _arena_after, aid, kind, prompt))


@app.get("/api/arena/{aid}")
def arena_get(aid: str):
    A = _arena(aid)
    return {k: _image(0, A["name"], A[k], f"/api/arena/{aid}/{k}") if A[k] is not None else None
            for k in ("before", "after")} | {"attack": A["attack"]}


@app.get("/api/arena/{aid}/{which}/{kind}.png")
def arena_png(aid: str, which: str, kind: str):
    r = _arena(aid).get(which) if which in ("before", "after") else None
    if r is None or kind not in ("photo", "heatmap"):
        raise ApiError(404, "not_found", "No such picture.")
    return _png(r.rgb if kind == "photo" else _arr(_sig(r.claim, "localizer"), "heatmap"))


# ---------------------------------------------------------------------------- reports
REPORTS = config.ROOT / "reports"


def _report(name: str) -> Path:
    p = REPORTS / name
    if not p.exists():
        raise ApiError(404, "not_found", f"{name} does not exist yet (make eval / make bench).")
    return p


@app.get("/api/reports/heldout")
def report_heldout():
    return json.loads(_report("heldout_table.json").read_text(encoding="utf-8"))


@app.get("/api/reports/eval")
def report_eval():
    return PlainTextResponse(_report("eval_latest.md").read_text(encoding="utf-8"),
                             media_type="text/markdown")


@app.get("/api/reports/medical_billing")
def report_medical_billing():
    return PlainTextResponse(_report("medical_billing.md").read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/reports/damage_story")
def report_damage_story():
    return PlainTextResponse(_report("damage_story.md").read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/reports/latency")
def report_latency():
    return PlainTextResponse(_report("latency_latest.md").read_text(encoding="utf-8"),
                             media_type="text/markdown")
