"""Reviewer UI (Phase 10): inbox → claim → Images · Documents · Score · Arena.

First open of a claim streams cards into the tabs as each check finishes, waits for the deep
tier, then stores the result in session state and redraws statically — sliders and buttons
never re-score. Uploads live in a temp dir that is wiped as soon as scoring ends.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # `streamlit run` from anywhere

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageDraw

from claimshield import audit, cases, config
from claimshield.arena import attacks
from claimshield.narrative import llm, template
from claimshield.pipeline import (combine, finish, score_document, score_identity, score_image,
                                  warm)
from claimshield.preprocess import prepare
from claimshield.signals.documents import ocr

BANDS = config.cfg("thresholds")["bands"]
BAND_COLOR = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red", "UNCERTAIN": "gray"}
CHIP = {"LOW": "🟢", "MEDIUM": "🟠", "HIGH": "🔴", "UNCERTAIN": "⚪"}
IMG_TYPES = ["jpg", "jpeg", "png", "heic", "heif", "webp"]
S = st.session_state


# ------------------------------------------------------------------------------ pieces
def card(s):
    with st.container(border=True):
        if s.score is None:
            state = "not applicable" if not s.applicable else "left out"
            st.markdown(f":gray[**{s.name}** · {state}]  \n:gray[{s.reason}]")
        else:
            c = "red" if s.score >= BANDS["medium_max"] else \
                "orange" if s.score >= BANDS["low_max"] else "green"
            st.markdown(f":{c}[**{s.name}** · {s.score:.2f}] · confidence {s.confidence:.2f}"
                        f"  \n{s.reason}")


def into(box):
    def on_card(s):
        with box:
            card(s)
    return on_card


def band_line(claim):
    st.markdown(f"### :{BAND_COLOR[claim.band]}[{claim.band}] · {claim.overall:.2f}")


def overlay(rgb, heat, alpha, regions=()):
    """Red heat over the photo; region boxes labelled A, B, …"""
    a = (np.clip(heat, 0, 1) * alpha)[..., None]
    out = np.asarray(rgb, np.float32) * (1 - a) + np.array([255, 0, 0], np.float32) * a
    img = Image.fromarray(out.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k, r in enumerate(regions):
        d.rectangle(r.box, outline=(255, 255, 0), width=3)
        d.text((r.box[0] + 4, r.box[1] + 2), chr(65 + k), fill=(255, 255, 0))
    return img


def ocr_boxes(page, words):
    img = page.copy()
    d = ImageDraw.Draw(img)
    for w in words:
        if w["page"] == 0:
            c = (0, 160, 0) if w["conf"] >= 80 else (230, 140, 0) if w["conf"] >= 60 else (220, 0, 0)
            d.rectangle(w["box"], outline=c, width=2)
    return img


def waterfall_fig(claim):
    names = [k for k, _ in claim.waterfall]
    vals = [v for _, v in claim.waterfall]
    fig = go.Figure(go.Waterfall(x=names + ["overall"], y=vals + [0],
                                 measure=["absolute"] + ["relative"] * (len(vals) - 1) + ["total"],
                                 decreasing={"marker": {"color": "#2e7d32"}},
                                 increasing={"marker": {"color": "#c62828"}}))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_range=[0, 1])
    return fig


def gauge_fig(claim):
    return go.Figure(go.Indicator(
        mode="gauge+number", value=claim.overall, number={"valueformat": ".2f"},
        gauge={"axis": {"range": [0, 1]}, "bar": {"color": "black"},
               "steps": [{"range": [0, BANDS["low_max"]], "color": "#c8e6c9"},
                         {"range": [BANDS["low_max"], BANDS["medium_max"]], "color": "#ffe0b2"},
                         {"range": [BANDS["medium_max"], 1], "color": "#ffcdd2"}]})
    ).update_layout(height=240, margin=dict(l=20, r=20, t=20, b=0))


def sunburst_fig(sb):
    return go.Figure(go.Sunburst(ids=sb["ids"], labels=sb["labels"], parents=sb["parents"],
                                 values=sb["values"], branchvalues="remainder")
                     ).update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))


def signal(res_claim, name):
    return next((s for s in res_claim.signals if s.name == name), None)


# ------------------------------------------------------------------------- tab renders
def render_image(i, res, name):
    st.markdown(f"#### Photo {i + 1} · {name}")
    left, right = st.columns([3, 2])
    loc, ae = signal(res.claim, "localizer"), signal(res.claim, "ae_reconstruction")
    with left:
        layer = st.radio("Overlay", ["localizer heatmap", "reconstruction map"], horizontal=True,
                         key=f"layer{i}", disabled=ae is None or "patch_map" not in ae.evidence)
        src = ae if layer == "reconstruction map" else loc
        heat = src.evidence.get("heatmap" if src is loc else "patch_map") if src else None
        alpha = st.slider("Heatmap", 0.0, 1.0, 0.5, key=f"alpha{i}")
        st.image(overlay(res.rgb, heat, alpha, res.claim.regions) if heat is not None else res.rgb)
        for r in res.claim.regions:
            st.markdown(f"- {r.reason}" + (" *(corroborated by the reconstruction test)*"
                                           if r.stage == 2 else ""))
        if res.quality_reasons:
            st.warning("Quality gate: " + "; ".join(res.quality_reasons))
    with right:
        for s in res.claim.signals:
            card(s)
        fam = signal(res.claim, "family_map")
        if fam and "sunburst" in fam.evidence:
            st.plotly_chart(sunburst_fig(fam.evidence["sunburst"]), use_container_width=True,
                            key=f"sun{i}")
        deep = f" · deep {res.t_deep:.1f} s" if res.t_deep is not None else ""
        st.caption(f"first card {res.t_first:.2f} s · fast tier {res.t_fast:.2f} s{deep}")


def render_doc(i, d, page, name):
    st.markdown(f"#### Document {i + 1} · {name} · {d.doc_type} · text from "
                f"{'OCR' if d.from_ocr else 'text layer'}")
    left, right = st.columns([3, 2])
    o = signal(d.claim, "ocr_confidence_dip")
    with left:
        if page is not None:
            words = o.evidence.get("words", []) if o else []
            st.image(ocr_boxes(page, words) if words else page)
            if words:
                st.caption("OCR boxes: green ≥ 80 confidence, orange ≥ 60, red below.")
        inc = signal(d.claim, "pdf_incremental_update")
        if inc and inc.evidence.get("diff"):
            st.markdown("**Version diff** — the file keeps its earlier revision")
            st.table([{"earlier version": a, "final version": b} for a, b in inc.evidence["diff"]])
        meta = signal(d.claim, "pdf_producer_mismatch")
        if meta and meta.evidence:
            e = meta.evidence
            st.markdown("**Metadata**")
            st.table([{"field": k, "value": str(e.get(k) or "—")} for k in
                      ("producer", "creator", "created", "modified", "days_between")])
        flags = [p for n in ("field_arithmetic", "field_dates", "field_format")
                 for p in (signal(d.claim, n).evidence.get("problems", []) if signal(d.claim, n) else [])]
        if flags:
            st.markdown("**Field flags**")
            for p in flags:
                st.markdown(f"- {p}")
    with right:
        for s in d.claim.signals:
            card(s)


def render_score(r, reviewer):
    case = r["case"]
    claim = case.claim
    if r.get("id_rgb") is not None:
        st.markdown("#### Identity")
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.image(r["id_rgb"], caption="ID")
        c2.image(r["selfie_rgb"], caption="Selfie")
        with c3:
            for s in claim.signals:
                if s.tier == "identity":
                    card(s)
    checks = [s for s in claim.signals if s.tier == "claim"]
    if checks:
        st.markdown("#### Claim-level checks")
        for s in checks:
            card(s)
    st.markdown("#### Score")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.plotly_chart(gauge_fig(claim), use_container_width=True, key="gauge")
        band_line(claim)
        lanes = {"image": claim.image_score, "document": claim.document_score,
                 "identity": claim.identity_score}
        st.caption(" · ".join(f"{k} {v:.2f}" for k, v in lanes.items() if v is not None))
    with c2:
        st.plotly_chart(waterfall_fig(claim), use_container_width=True, key="waterfall")
    st.info(r["narrative"])
    st.caption("Narrative: " + ("LLM rewrite of the template (numbers checked)" if r["llm"]
                                else "template"))

    st.markdown("#### Decision")
    note = st.text_input("Note (optional)", key=f"note_{r['id']}")
    cols = st.columns(3)
    for col, action in zip(cols, audit.ACTIONS):
        if col.button(action.capitalize(), key=f"{action}_{r['id']}", use_container_width=True):
            audit.record(r["id"], r["hashes"], claim, reviewer, action, note)
            st.success(f"Recorded: {action} by {reviewer}.")
    hist = audit.history(r["id"])
    if hist:
        st.table(hist)


# ------------------------------------------------------------------------ scoring runs
def run_case(case, tabs):
    """Stream every lane into its tab, then combine, wait for the deep tier, narrate."""
    with tabs[0]:
        img_boxes = []
        for p in case.photos:
            st.markdown(f"#### {Path(p).name}")
            img_boxes.append(st.container())
    with tabs[1]:
        doc_boxes = []
        for p in case.docs:
            st.markdown(f"#### {Path(p).name}")
            doc_boxes.append(st.container())
    with tabs[2]:
        id_box, score_box = st.container(), st.empty()

    images = [score_image(p, on_card=into(b)) for p, b in zip(case.photos, img_boxes)]
    docs = [score_document(p, on_card=into(b)) for p, b in zip(case.docs, doc_boxes)]
    identity, id_text = (score_identity(case.id_path, case.selfie, on_card=into(id_box))
                         if case.id_path and case.selfie else ([], ""))
    with score_box.container():
        band_line(combine(images, docs, identity, id_text, case_id=case.id, story=case.description).claim)
        st.info("Deep scan running… (reconstruction test; the score updates when it lands)")
    images = [finish(r) for r in images]
    res = combine(images, docs, identity, id_text, case_id=case.id, remember=True,
                  story=case.description)

    pages = []
    for p, d in zip(case.docs, docs):
        page = d.page
        if page is None and p.lower().endswith(".pdf"):
            try:  # a text-layer PDF still gets a picture (needs Poppler)
                page = ocr.render(Path(p).read_bytes())[0]
            except Exception:
                page = None
        pages.append(page)
    out = llm.result(llm.start(res.narrative))  # only placeholder text leaves the process
    S.results[case.id] = {
        "id": case.id, "title": case.title, "case": res, "pages": pages,
        "names": [Path(p).name for p in case.photos], "doc_names": [Path(p).name for p in case.docs],
        "hashes": cases.hashes(case), "llm": bool(out),
        "narrative": template.fill(out or res.narrative, res.pii),
        "id_rgb": prepare(case.id_path).rgb if case.id_path and case.selfie else None,
        "selfie_rgb": prepare(case.selfie).rgb if case.id_path and case.selfie else None}
    cases.save_band(case.id, res.claim.band)


def open_upload(case_id, tabs):
    """Uploads → temp dir with role-based names → score → wiped."""
    up = S.pop("upload")
    with tempfile.TemporaryDirectory() as d:
        for name, data in up:
            (Path(d) / name).write_bytes(data)
        run_case(cases.load(Path(d), case_id), tabs)


# ------------------------------------------------------------------------------- arena
def arena_tab():
    st.markdown("### Red-team arena")
    st.caption("Score a real photo, fabricate damage on it, and score it again.")
    src = st.radio("Photo", ["Upload", "Seed photo"], horizontal=True, key="arena_src")
    data = name = None
    if src == "Upload":
        f = st.file_uploader("Photo", type=IMG_TYPES, key="arena_up")
        if f:
            data, name = f.getvalue(), f.name
    else:
        seeds = sorted(p for p in (config.ROOT / "data" / "seeds").glob("*")
                       if p.suffix.lower()[1:] in IMG_TYPES)[:50] if (config.ROOT / "data" / "seeds").exists() else []
        if seeds:
            p = st.selectbox("Seed", seeds, format_func=lambda p: p.name)
            data, name = p.read_bytes(), p.name
        else:
            st.info("No seed photos in data/seeds.")
    if data is None:
        return heldout_tables()
    key = hashlib.sha256(data).hexdigest()
    A = S.arena if S.get("arena", {}).get("key") == key else {"key": key}
    S.arena = A
    suffix = Path(name).suffix.lower()

    if "before" not in A and st.button("Score photo", type="primary"):
        box = st.container()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / f"photo{suffix}"
            p.write_bytes(data)
            A["before"] = finish(score_image(str(p), on_card=into(box)))
        st.rerun()

    if "before" in A:
        kind = st.radio("Attack", list(attacks.ATTACKS), horizontal=True, key="arena_kind")
        prompt = st.text_input("Damage to paint", attacks._cfg()["prompt"]) if kind == "inpaint" else None
        if st.button("Attack", type="primary"):
            box = st.container()
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / f"photo{suffix}"
                p.write_bytes(data)
                try:
                    with st.spinner("Fabricating…"):
                        atk = attacks.inpaint(p, prompt) if kind == "inpaint" else attacks.ATTACKS[kind](p)
                except RuntimeError as e:
                    st.error(str(e))
                    return heldout_tables()
                q = Path(d) / "attacked.jpg"
                q.write_bytes(atk.data)
                A["after"] = finish(score_image(str(q), on_card=into(box)))
                A["atk"] = atk
            st.rerun()

        c1, c2 = st.columns(2)
        for col, key_, title in ((c1, "before", "Original"), (c2, "after", "Attacked")):
            res = A.get(key_)
            if res is None:
                continue
            with col:
                st.markdown(f"#### {title}")
                loc = signal(res.claim, "localizer")
                heat = loc.evidence.get("heatmap") if loc else None
                st.image(overlay(res.rgb, heat, 0.4, res.claim.regions) if heat is not None else res.rgb)
                band_line(res.claim)
                for r in res.claim.regions:
                    st.markdown(f"- {r.reason}")
                fam = signal(res.claim, "family_map")
                if fam:
                    st.caption(f"Family map: {fam.reason}")
                with st.expander("Signal cards"):
                    for s in res.claim.signals:
                        card(s)
        if "atk" in A:
            atk = A["atk"]
            st.caption(f"{atk.note} ({atk.method}, {atk.seconds:.1f} s)")
    heldout_tables()


def heldout_tables():
    p = config.ROOT / "reports" / "heldout_table.json"
    if not p.exists():
        st.caption("Held-out table: run `make eval` to produce reports/heldout_table.json.")
        return
    t = json.loads(p.read_text(encoding="utf-8"))
    label = {"sd15": "SD 1.5", "sdxl": "SDXL", "nova": "Nova Canvas",
             "flux": "Flux — never trained or calibrated on", "gan": "GAN — eval-only (reconstruction blind spot)"}
    f2 = lambda v: "—" if v is None else f"{v:.2f}"  # noqa: E731
    st.markdown("#### Detection by generator family (test set)")
    st.table([{"family": label[k], "n": v["n"], "AUC": f2(v["auc"]), "TPR @ 1 % FPR": f2(v["tpr_at_1fpr"]),
               "flagged HIGH": f2(v["flagged_high"])} for k, v in t["families"].items() if v["n"]])
    st.markdown("#### Robustness (composite AUC by quality)")
    st.table([{q: f2(v) for q, v in t["robustness"].items()}])


# -------------------------------------------------------------------------------- page
st.set_page_config(page_title="ClaimShield", layout="wide")
S.setdefault("results", {})
for problem in st.cache_resource(warm)():  # pre-warm once per server, before any upload
    st.sidebar.warning(f"Model not ready — {problem}")

with st.sidebar:
    st.title("ClaimShield")
    reviewer = st.text_input("Reviewer", "reviewer")
    st.markdown("#### Inbox")
    bands = cases.last_bands()
    for c in cases.inbox():
        chip = CHIP.get(bands.get(c.id), "·")
        if st.button(f"{chip} {c.title}", key=f"open_{c.id}", use_container_width=True):
            S.open = c.id
    with st.expander("New claim from files"):
        photos = st.file_uploader("Damage photos", type=IMG_TYPES, accept_multiple_files=True)
        docs = st.file_uploader("Documents (PDF or scan)", type=["pdf", *IMG_TYPES],
                                accept_multiple_files=True)
        idf = st.file_uploader("ID document", type=IMG_TYPES)
        selfie = st.file_uploader("Selfie", type=IMG_TYPES)
        if st.button("Score claim", disabled=not (photos or docs)):
            files = ([(f"photo_{i}{Path(f.name).suffix.lower()}", f.getvalue()) for i, f in enumerate(photos)]
                     + [(f"doc_{i}{Path(f.name).suffix.lower()}", f.getvalue()) for i, f in enumerate(docs)]
                     + [(f"{role}{Path(f.name).suffix.lower()}", f.getvalue())
                        for role, f in (("id", idf), ("selfie", selfie)) if f])
            S.upload = files
            S.open = "upload-" + hashlib.sha256(b"".join(d for _, d in files)).hexdigest()[:8]

tabs = st.tabs(["Images", "Documents", "Score", "Arena"])
cid = S.get("open")
if cid and cid not in S.results:
    if cid.startswith("upload-"):
        if "upload" in S:
            open_upload(cid, tabs)
        else:  # uploads were wiped (e.g. server restart): nothing left to score
            S.open = None
    else:
        run_case(next(c for c in cases.inbox() if c.id == cid), tabs)
    st.rerun()
elif cid:
    r = S.results[cid]
    with tabs[0]:
        st.markdown(f"## {r['title']}")
        for i, (res, n) in enumerate(zip(r["case"].images, r["names"])):
            render_image(i, res, n)
        if not r["case"].images:
            st.info("No photos in this claim.")
    with tabs[1]:
        for i, (d, page, n) in enumerate(zip(r["case"].documents, r["pages"], r["doc_names"])):
            render_doc(i, d, page, n)
        if not r["case"].documents:
            st.info("No documents in this claim.")
    with tabs[2]:
        render_score(r, reviewer)
else:
    for t in tabs[:3]:
        t.info("Open a claim from the inbox, or upload one in the sidebar.")
with tabs[3]:
    arena_tab()
