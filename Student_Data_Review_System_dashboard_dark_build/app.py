"""
Student Data Review System — Streamlit App
Original + Persistence Fix (Data no longer clears when switching pages)
"""

import csv
import io
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.cleaning_logic.Student_attendance import clean_attendance_data
from scripts.cleaning_logic.Student_performance import clean_student_performance
from scripts.cleaning_logic.Student_profiles import clean_student_profiles
from scripts.validation.validator import (
    validate_attendance,
    validate_performance,
    validate_profiles,
)
from dashboard.dashboard import render_dashboard


# ── directories ───────────────────────────────────────────────────────────────
for d in (ROOT / "data" / "raw", ROOT / "data" / "cleaned", ROOT / "scripts" / "logs", ROOT / "data" / "local_store"):
    d.mkdir(parents=True, exist_ok=True)

RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "cleaned"
LOCAL_STORE_DIR = ROOT / "data" / "local_store"
SNAPSHOT_DIR = LOCAL_STORE_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_STATE_FILE = LOCAL_STORE_DIR / "app_state.json"
LATEST_REVIEW_FILE = LOCAL_STORE_DIR / "latest_review.json"


# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Student Data Review System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── global css / dark theme ─────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

:root{
    --bg:#040b16;
    --bg-soft:#08111f;
    --panel:#091424;
    --panel-2:#0b172a;
    --line:#18314f;
    --line-2:#1f3653;
    --text:#eef4ff;
    --muted:#8fa3bf;
    --blue:#3b82f6;
    --green:#22c55e;
    --purple:#8b5cf6;
    --orange:#f59e0b;
    --red:#ef4444;
}

.stApp { background: radial-gradient(circle at top left, #071120 0%, #040a14 45%, #02060d 100%); color: var(--text); }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#040b16 0%, #07111e 100%);
    border-right:1px solid var(--line);
}
section[data-testid="stSidebar"] * { color: var(--text); }

.block-container { padding-top: 1.35rem; }

.brand-wrap {
    display:flex; align-items:center; gap:14px; margin-bottom:1rem;
    background:linear-gradient(180deg, rgba(7,16,30,.95), rgba(4,10,20,.95));
    border:1px solid var(--line); border-radius:18px; padding:16px;
}
.brand-icon {
    width:54px; height:54px; border-radius:16px;
    display:flex; align-items:center; justify-content:center;
    background:linear-gradient(180deg,#1d4ed8,#2563eb); color:white; font-size:1.7rem;
    box-shadow:0 10px 20px rgba(37,99,235,.25);
}
.brand-title { font-size:1.25rem; font-weight:800; line-height:1.1; color:#f8fbff; }
.brand-sub { font-size:.82rem; color:#60a5fa; margin-top:4px; }

.nav-note {
    font-size:.78rem; color:var(--muted); margin:.35rem 0 .5rem 0; text-transform:uppercase; letter-spacing:.08em;
}

.header-bar {
    background: linear-gradient(135deg,#040b16,#091225 50%,#050d19);
    border:1px solid var(--line-2);
    box-shadow:0 12px 30px rgba(0,0,0,.32);
    padding:1.7rem 1.8rem; border-radius:20px; margin-bottom:1.1rem; color:white;
}
.header-bar h1 { color:white; margin:0 0 .35rem 0; font-size:2rem; font-weight:800; }
.header-bar p { color:var(--muted); margin:0; font-size:1rem; }

.file-card, .step-card, .hist-row {
    background:linear-gradient(180deg, rgba(9,20,36,.95), rgba(7,17,31,.95));
    border:1px solid var(--line);
    border-radius:14px;
    box-shadow:0 8px 24px rgba(0,0,0,.22);
}
.file-card { padding:1rem 1.15rem; margin-bottom:.7rem; }
.file-card .fname { font-weight:700; color:#f3f8ff; font-size:.96rem; }
.file-card .fmeta { font-size:.8rem; color:var(--muted); margin-top:.2rem; }

.badge {
    display:inline-block; padding:.22rem .68rem; border-radius:999px; font-size:.73rem;
    font-weight:700; letter-spacing:.03em; margin-right:.32rem;
}
.badge-profiles    { background:rgba(59,130,246,.18); color:#93c5fd; border:1px solid rgba(59,130,246,.24); }
.badge-performance { background:rgba(139,92,246,.18); color:#c4b5fd; border:1px solid rgba(139,92,246,.24); }
.badge-attendance  { background:rgba(245,158,11,.18); color:#fcd34d; border:1px solid rgba(245,158,11,.24); }
.badge-unknown     { background:rgba(239,68,68,.18); color:#fca5a5; border:1px solid rgba(239,68,68,.24); }
.badge-ok          { background:rgba(34,197,94,.18); color:#86efac; border:1px solid rgba(34,197,94,.24); }
.badge-warn        { background:rgba(245,158,11,.18); color:#fcd34d; border:1px solid rgba(245,158,11,.24); }
.badge-err         { background:rgba(239,68,68,.18); color:#fca5a5; border:1px solid rgba(239,68,68,.24); }

.issue-item {
    padding:.55rem .8rem; border-radius:10px; margin:.28rem 0; font-size:.88rem; border:1px solid var(--line);
}
.issue-ok   { background:rgba(34,197,94,.08); color:#9ae6b4; }
.issue-warn { background:rgba(245,158,11,.08); color:#fcd34d; }

.metric-box {
    background:linear-gradient(180deg, rgba(10,20,36,.96), rgba(8,15,27,.98));
    border:1px solid var(--line); border-radius:12px; padding:1rem; text-align:center; min-height:96px;
}
.metric-box .val { font-size:1.75rem; font-weight:800; color:#60a5fa; }
.metric-box .lbl { font-size:.8rem; color:var(--muted); margin-top:.24rem; }

.hist-row { display:flex; align-items:center; gap:.75rem; padding:.62rem .8rem; margin-bottom:.45rem; font-size:.84rem; }
.hist-row .ht { color:var(--muted); min-width:132px; }
.hist-row .hf { color:#eff6ff; flex:1; }
.hist-row .hm { color:#7488a5; font-size:.76rem; }

.step-card {
    border-left:4px solid #2563eb; padding:1rem 1.15rem; margin-bottom:.75rem; color:#e8f0ff;
}
.step-card b { color:#7dd3fc; }
.step-card small { color:var(--muted); }
</style>
""",
    unsafe_allow_html=True,
)


# ── Persistence Fix ─────────────────────────────────────────────────────────
def _load_local_store() -> dict:
    if not LOCAL_STATE_FILE.exists():
        return {}
    try:
        with LOCAL_STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _load_latest_review_store() -> dict:
    if not LATEST_REVIEW_FILE.exists():
        return {}
    try:
        with LATEST_REVIEW_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_json_file(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp_path.replace(path)

def restore_local_store_into_session(force: bool = True):
    store = _load_local_store()
    review_store = _load_latest_review_store()

    if force or len(st.session_state.get("results", [])) == 0:
        saved_results = review_store.get("results") or store.get("results", [])
        if saved_results:
            st.session_state.results = saved_results

    if store.get("history"):
        st.session_state.history = store.get("history", [])
    if store.get("last_page"):
        st.session_state.last_page = store.get("last_page", "Upload & Review")


def persist_local_store():
    current_results = st.session_state.get("results", [])
    current_history = st.session_state.get("history", [])

    payload = {
        "schema_version": 2,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_page": st.session_state.get("last_page", "Upload & Review"),
        "history": current_history,
        "results": current_results,
    }

    try:
        _write_json_file(LOCAL_STATE_FILE, payload)
        if current_results:
            _write_json_file(LATEST_REVIEW_FILE, {"results": current_results})
    except Exception as e:
        st.warning(f"Local activity memory could not be saved: {e}")


# ── session state ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
if "history" not in st.session_state:
    st.session_state.history = []
if "last_page" not in st.session_state:
    st.session_state.last_page = "Upload & Review"

restore_local_store_into_session(force=True)


# ═════════════════════════════════════════════════════════════════════════════
# FUZZY CLASSIFIER (Original)
# ═════════════════════════════════════════════════════════════════════════════
EXPECTED = {
    "profiles": {"student_id", "student_name", "class", "gender", "guardian_contact"},
    "performance": {
        "record_id", "student_id", "student_name", "class", "gender", "term",
        "subject", "attendance_percent", "assignment_score", "quiz_score",
        "exam_score", "total_score", "result", "study_hours", "teacher_comment",
    },
    "attendance": {
        "attendance_id", "student_id", "student_name", "class", "term",
        "days_present", "days_absent", "total_school_days", "attendance_percent",
    },
}


def fuzzy_classify(df: pd.DataFrame):
    cols = set(df.columns.str.strip().str.lower().str.replace(" ", "_"))
    best_type, best_score, best_miss, best_extra = None, 0.0, set(), set()

    for dtype, expected in EXPECTED.items():
        intersection = cols & expected
        union = cols | expected
        score = len(intersection) / len(union) if union else 0
        if score > best_score:
            best_type, best_score = dtype, score
            best_miss = expected - cols
            best_extra = cols - expected

    if best_score < 0.55:
        raise ValueError(f"No dataset type matched well enough (best score {best_score:.0%}).")
    return best_type, best_score, best_miss, best_extra


BADGE_HTML = {
    "profiles": '<span class="badge badge-profiles">👤 Profiles</span>',
    "performance": '<span class="badge badge-performance">📊 Performance</span>',
    "attendance": '<span class="badge badge-attendance">📅 Attendance</span>',
}

VALIDATE_FN = {
    "profiles": validate_profiles,
    "performance": validate_performance,
    "attendance": validate_attendance,
}

CLEAN_FN = {
    "profiles": clean_student_profiles,
    "performance": clean_student_performance,
    "attendance": clean_attendance_data,
}


def capture_clean(fn, path):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        res = fn(path)
    except Exception:
        sys.stdout = old
        raise
    finally:
        sys.stdout = old
    return res, buf.getvalue()


def save_raw(uploaded_file) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = Path(uploaded_file.name).stem
    dest = RAW_DIR / f"{stem}_{ts}.csv"
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def build_comparison(raw_df, cleaned_df):
    shared = [c for c in cleaned_df.columns if c in raw_df.columns]
    r = raw_df[shared].reset_index(drop=True).astype(str)
    c = cleaned_df[shared].reset_index(drop=True).astype(str)
    n = min(len(r), len(c))
    r, c = r.iloc[:n], c.iloc[:n]
    changed = r != c

    def hl(data):
        s = pd.DataFrame("", index=data.index, columns=data.columns)
        for col in data.columns:
            if col in changed.columns:
                s.loc[changed[col], col] = "background-color:#fef08a;color:#713f12;"
        return s

    return c.style.apply(hl, axis=None), changed.any(axis=1).sum(), changed.sum().sum()


def issues_to_csv_bytes(issues: list, filename: str, dataset_type: str) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "dataset_type", "issue"])
    for issue in issues:
        w.writerow([filename, dataset_type, issue])
    return buf.getvalue().encode()


def run_pipeline(uploaded_file) -> dict:
    res = {
        "filename": uploaded_file.name,
        "success": False,
        "dataset_type": None,
        "match_score": None,
        "fuzzy_notes": [],
        "issues": [],
        "raw_df": None,
        "cleaned_df": None,
        "raw_rows": 0,
        "logs": "",
        "error": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        raw_df = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
    except Exception as e:
        res["error"] = f"Could not read CSV: {e}"
        return res

    res["raw_rows"] = len(raw_df)
    res["raw_df"] = raw_df.copy()

    norm_df = raw_df.copy()
    norm_df.columns = norm_df.columns.str.strip().str.lower().str.replace(" ", "_")

    try:
        dtype, score, missing, extra = fuzzy_classify(norm_df)
        res["dataset_type"] = dtype
        res["match_score"] = score
        if missing:
            res["fuzzy_notes"].append(f"Columns not found (assumed OK): {', '.join(sorted(missing))}")
        if extra:
            res["fuzzy_notes"].append(f"Extra columns ignored: {', '.join(sorted(extra))}")
    except ValueError as e:
        res["error"] = str(e)
        return res

    try:
        res["issues"] = VALIDATE_FN[dtype](norm_df)
    except Exception as e:
        res["issues"] = [f"Validator error: {e}"]

    try:
        raw_path = save_raw(uploaded_file)
        cleaned_df, logs = capture_clean(CLEAN_FN[dtype], raw_path)
        res["cleaned_df"] = cleaned_df
        res["logs"] = logs
        res["success"] = True
    except Exception as e:
        res["error"] = f"Cleaning failed: {e}\n\n{traceback.format_exc()}"

    return res


# ═════════════════════════════════════════════════════════════════════════════
# PAGE RENDERERS (Original)
# ═════════════════════════════════════════════════════════════════════════════
def render_review_results(results: list):
    if not results:
        return

    st.markdown("---")
    st.markdown("## Results")

    for res in results:
        fname = res.get("filename", "Uploaded file")

        with st.expander(f"{'✅' if res.get('success') else '❌'} {fname}", expanded=True):
            if res.get("error"):
                st.error(f"Pipeline failed for **{fname}**")
                st.code(res.get("error"))
                continue

            dtype = res.get("dataset_type")
            badge = BADGE_HTML.get(dtype, f'<span class="badge badge-unknown">{dtype}</span>')
            score = res.get("match_score")
            score_pct = f"{score:.0%}" if isinstance(score, (int, float)) else "—"

            st.markdown(
                f"**Step 1 — Dataset type** &nbsp; {badge} &nbsp;"
                f"<span class='badge badge-ok'>Match {score_pct}</span>",
                unsafe_allow_html=True,
            )

            for note in res.get("fuzzy_notes", []):
                st.markdown(f'<div class="issue-item issue-warn">🔍 {note}</div>', unsafe_allow_html=True)

            st.markdown("**Step 2 — Validation report**")
            issues = res.get("issues", [])

            if not issues:
                st.markdown('<div class="issue-item issue-ok">✅ No issues found.</div>', unsafe_allow_html=True)
            else:
                for issue in issues:
                    st.markdown(f'<div class="issue-item issue-warn">⚠️ {issue}</div>', unsafe_allow_html=True)

            report_bytes = issues_to_csv_bytes(issues, fname, dtype or "unknown")
            st.download_button(
                label="⬇️ Download validation report",
                data=report_bytes,
                file_name=f"{Path(fname).stem}_validation_report.csv",
                mime="text/csv",
                key=f"val_saved_{fname}",
            )

            raw_df = res.get("raw_df")
            cleaned_df = res.get("cleaned_df")

            if not isinstance(raw_df, pd.DataFrame) or not isinstance(cleaned_df, pd.DataFrame):
                continue

            st.markdown("**Step 3 — Before / After**")

            rows_before = int(res.get("raw_rows", len(raw_df)) or 0)
            rows_after = len(cleaned_df)
            rows_removed = rows_before - rows_after

            styled_clean, rows_changed, cells_changed = build_comparison(raw_df, cleaned_df)

            m1, m2, m3, m4, m5 = st.columns(5)
            for col_obj, val, label in [
                (m1, f"{rows_before:,}", "Rows original"),
                (m2, f"{rows_after:,}", "Rows cleaned"),
                (m3, f"{rows_removed:,}", "Rows removed"),
                (m4, f"{rows_changed:,}", "Rows changed"),
                (m5, f"{cells_changed:,}", "Cells changed"),
            ]:
                col_obj.markdown(
                    f'<div class="metric-box"><div class="val">{val}</div><div class="lbl">{label}</div></div>',
                    unsafe_allow_html=True,
                )

            tab_b, tab_a = st.tabs(["📋 Before (raw)", "✅ After (cleaned)"])
            with tab_b:
                st.caption(f"{rows_before:,} rows · {raw_df.shape[1]} columns")
                st.dataframe(raw_df.head(20), use_container_width=True)
            with tab_a:
                st.caption(f"{rows_after:,} rows · 🟡 yellow cells were changed")
                st.dataframe(styled_clean, use_container_width=True)

            csv_bytes = cleaned_df.to_csv(index=False).encode()
            ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="⬇️ Download Cleaned CSV",
                data=csv_bytes,
                file_name=f"{dtype}_cleaned_{ts_label}.csv",
                mime="text/csv",
                key=f"dl_saved_{fname}",
                use_container_width=True,
            )


def render_upload_and_review():
    st.markdown(
        """
        <div class="header-bar">
          <h1>🎓 Student Data Review System</h1>
          <p>Upload one or more CSV files — the pipeline will classify, validate, and clean each one automatically.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Drop your CSV files here (you can select multiple)",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload Student Profiles, Performance, and/or Attendance files together.",
        key="csv_multi_uploader",
    )

    if uploaded_files:
        if st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
            results = []
            progress = st.progress(0, text="Starting…")

            for i, f in enumerate(uploaded_files):
                progress.progress(int((i / len(uploaded_files)) * 100), text=f"Processing {f.name}…")
                f.seek(0)
                r = run_pipeline(f)
                results.append(r)
                st.session_state.history.append({
                    "timestamp": r["timestamp"],
                    "filename": r["filename"],
                    "dataset_type": r["dataset_type"],
                    "raw_rows": r["raw_rows"],
                    "success": r["success"],
                })

            progress.progress(100, text="Done ✅")
            st.session_state.results = results
            persist_local_store()
            st.success("Pipeline completed and saved to local activity memory.")

    render_review_results(st.session_state.get("results", []))


# Sidebar + Navigation
with st.sidebar:
    st.markdown(
        """
        <div class="brand-wrap">
            <div class="brand-icon">🎓</div>
            <div>
                <div class="brand-title">Student Data</div>
                <div class="brand-sub">Review System</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="nav-note">Navigation</div>', unsafe_allow_html=True)
    pages = ["Upload & Review", "Dashboard", "Cleaned Files", "About System"]
    page = st.radio(
        "Go to",
        pages,
        index=pages.index(st.session_state.get("last_page", "Upload & Review")),
        label_visibility="collapsed",
        key="current_page_radio",
    )
    st.session_state.last_page = page

    st.markdown("---")
    st.markdown("### 🕑 Upload History")
    if not st.session_state.history:
        st.caption("No runs yet — history appears here after processing.")
    else:
        for entry in reversed(st.session_state.history[-8:]):
            status = "✅" if entry.get("success") else "❌"
            st.markdown(
                f"""
                <div class="hist-row">
                  <span class="ht">{entry.get('timestamp')}</span>
                  <span class="hf">{status} {entry.get('filename')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.button("Clear saved local activity", use_container_width=True):
        st.session_state.results = []
        st.session_state.history = []
        st.session_state.last_page = "Upload & Review"
        if LOCAL_STATE_FILE.exists():
            LOCAL_STATE_FILE.unlink()
        if LATEST_REVIEW_FILE.exists():
            LATEST_REVIEW_FILE.unlink()
        st.rerun()

# ── route pages ───────────────────────────────────────────────────────────────
if page == "Upload & Review":
    render_upload_and_review()
elif page == "Dashboard":
    render_dashboard(st.session_state.results)
elif page == "Cleaned Files":
    st.write("### Cleaned Files Page")
    # You can expand this later
else:
    st.write("### About System")

persist_local_store()

st.markdown("---")
st.caption("Student Data Review System · Built with Streamlit")
