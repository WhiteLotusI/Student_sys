"""
Student Data Review System — Final Fixed Version
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

# ====================== DIRECTORIES ======================
for d in (ROOT / "data" / "raw", ROOT / "data" / "cleaned", ROOT / "scripts" / "logs", ROOT / "data" / "local_store"):
    d.mkdir(parents=True, exist_ok=True)

RAW_DIR = ROOT / "data" / "raw"
LOCAL_STORE_DIR = ROOT / "data" / "local_store"
SNAPSHOT_DIR = LOCAL_STORE_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_STATE_FILE = LOCAL_STORE_DIR / "app_state.json"
LATEST_REVIEW_FILE = LOCAL_STORE_DIR / "latest_review.json"

# ====================== PAGE CONFIG & CSS ======================
st.set_page_config(page_title="Student Data Review System", page_icon="🎓", layout="wide")

st.markdown(
    """
<style>
.stApp { background: radial-gradient(circle at top left, #071120 0%, #040a14 45%, #02060d 100%); color: #eef4ff; }
</style>
""", 
    unsafe_allow_html=True
)

# ====================== PERSISTENCE ======================
def _safe_name(value: str) -> str:
    text = str(value or "item").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:80] or "item"

def _load_local_store():
    if not LOCAL_STATE_FILE.exists(): return {}
    try:
        with open(LOCAL_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def _load_latest_review():
    if not LATEST_REVIEW_FILE.exists(): return {}
    try:
        with open(LATEST_REVIEW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def _write_json_file(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)

def _restore_dataframe(rel_path):
    if not rel_path: return None
    try:
        return pd.read_csv(ROOT / rel_path)
    except: return None

def _restore_results(saved_results):
    restored = []
    for item in saved_results or []:
        restored.append({
            "filename": item.get("filename"),
            "success": item.get("success", False),
            "dataset_type": item.get("dataset_type"),
            "match_score": item.get("match_score"),
            "fuzzy_notes": item.get("fuzzy_notes", []),
            "issues": item.get("issues", []),
            "raw_df": _restore_dataframe(item.get("raw_snapshot")),
            "cleaned_df": _restore_dataframe(item.get("cleaned_snapshot")),
            "raw_rows": item.get("raw_rows", 0),
            "logs": item.get("logs", ""),
            "error": item.get("error"),
            "timestamp": item.get("timestamp"),
            "persist_id": item.get("persist_id"),
            "raw_snapshot": item.get("raw_snapshot"),
            "cleaned_snapshot": item.get("cleaned_snapshot"),
        })
    return restored

def _snapshot_dataframe(df, persist_id: str, suffix: str):
    if not isinstance(df, pd.DataFrame): return None
    path = SNAPSHOT_DIR / f"{persist_id}_{suffix}.csv"
    df.to_csv(path, index=False)
    return str(path.relative_to(ROOT))

def _serialize_results(results):
    serialized = []
    for idx, r in enumerate(results or []):
        persist_id = r.get("persist_id") or _safe_name(f"{idx}_{r.get('dataset_type')}")
        raw_snap = r.get("raw_snapshot") or _snapshot_dataframe(r.get("raw_df"), persist_id, "raw")
        clean_snap = r.get("cleaned_snapshot") or _snapshot_dataframe(r.get("cleaned_df"), persist_id, "cleaned")
        
        serialized.append({
            "filename": r.get("filename"),
            "success": r.get("success", False),
            "dataset_type": r.get("dataset_type"),
            "match_score": r.get("match_score"),
            "fuzzy_notes": r.get("fuzzy_notes", []),
            "issues": r.get("issues", []),
            "raw_rows": r.get("raw_rows", 0),
            "logs": r.get("logs", ""),
            "error": r.get("error"),
            "timestamp": r.get("timestamp"),
            "persist_id": persist_id,
            "raw_snapshot": raw_snap,
            "cleaned_snapshot": clean_snap,
        })
    return serialized

def persist_local_store():
    results = st.session_state.get("results", [])
    history = st.session_state.get("history", [])
    payload = {
        "schema_version": 2,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_page": st.session_state.get("last_page", "Upload & Review"),
        "history": history,
        "results": _serialize_results(results),
    }
    try:
        _write_json_file(LOCAL_STATE_FILE, payload)
        if results:
            _write_json_file(LATEST_REVIEW_FILE, {"results": _serialize_results(results)})
    except: pass

def restore_local_store_into_session():
    review = _load_latest_review()
    if review.get("results"):
        st.session_state.results = _restore_results(review["results"])
    elif _load_local_store().get("results"):
        st.session_state.results = _restore_results(_load_local_store()["results"])

# ====================== INITIALIZE ======================
for key in ["results", "history", "last_page"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key != "last_page" else "Upload & Review"

restore_local_store_into_session()

# ====================== PIPELINE ======================
EXPECTED = {
    "profiles": {"student_id", "student_name", "class", "gender", "guardian_contact"},
    "performance": {"record_id", "student_id", "student_name", "class", "gender", "term", "subject", "attendance_percent", "assignment_score", "quiz_score", "exam_score", "total_score", "result", "study_hours", "teacher_comment"},
    "attendance": {"attendance_id", "student_id", "student_name", "class", "term", "days_present", "days_absent", "total_school_days", "attendance_percent"},
}

BADGE_HTML = {
    "profiles": '<span class="badge badge-profiles">👤 Profiles</span>',
    "performance": '<span class="badge badge-performance">📊 Performance</span>',
    "attendance": '<span class="badge badge-attendance">📅 Attendance</span>',
}

VALIDATE_FN = {"profiles": validate_profiles, "performance": validate_performance, "attendance": validate_attendance}
CLEAN_FN = {"profiles": clean_student_profiles, "performance": clean_student_performance, "attendance": clean_attendance_data}

def fuzzy_classify(df: pd.DataFrame):
    cols = set(df.columns.str.strip().str.lower().str.replace(" ", "_"))
    best_type, best_score = None, 0.0
    for dtype, expected in EXPECTED.items():
        score = len(cols & expected) / len(cols | expected) if (cols | expected) else 0
        if score > best_score:
            best_type, best_score = dtype, score
    if best_score < 0.55:
        raise ValueError(f"No dataset matched well enough (score: {best_score:.0%})")
    return best_type, best_score

def capture_clean(fn, path):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        res = fn(path)
        return res, buf.getvalue()
    finally:
        sys.stdout = old

def run_pipeline(uploaded_file) -> dict:
    res = {
        "filename": uploaded_file.name, "success": False, "dataset_type": None,
        "match_score": None, "fuzzy_notes": [], "issues": [], "raw_df": None,
        "cleaned_df": None, "raw_rows": 0, "logs": "", "error": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        raw_df = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
        res["raw_df"] = raw_df.copy()
        res["raw_rows"] = len(raw_df)
    except Exception as e:
        res["error"] = f"Read error: {e}"
        return res

    norm_df = raw_df.copy()
    norm_df.columns = norm_df.columns.str.strip().str.lower().str.replace(" ", "_")

    try:
        dtype, score = fuzzy_classify(norm_df)
        res["dataset_type"] = dtype
        res["match_score"] = score
    except ValueError as e:
        res["error"] = str(e)
        return res

    try:
        res["issues"] = VALIDATE_FN[dtype](norm_df)
    except Exception as e:
        res["issues"] = [f"Validation error: {e}"]

    try:
        raw_path = RAW_DIR / f"{Path(uploaded_file.name).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        raw_path.write_bytes(uploaded_file.getbuffer())
        cleaned_df, logs = capture_clean(CLEAN_FN[dtype], raw_path)
        res["cleaned_df"] = cleaned_df
        res["logs"] = logs
        res["success"] = True
    except Exception as e:
        res["error"] = f"Cleaning failed: {e}"

    return res

# ====================== RENDER FUNCTIONS ======================
def render_upload_and_review():
    st.markdown("### Upload & Review")
    uploaded_files = st.file_uploader("Drop CSV files here (multiple allowed)", type=["csv"], accept_multiple_files=True)

    if uploaded_files and st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
        results = []
        progress = st.progress(0)
        for i, f in enumerate(uploaded_files):
            progress.progress((i+1)/len(uploaded_files), text=f"Processing {f.name}...")
            r = run_pipeline(f)
            results.append(r)
            st.session_state.history.append({
                "timestamp": r["timestamp"], "filename": r["filename"],
                "dataset_type": r.get("dataset_type"), "success": r.get("success", False)
            })
        st.session_state.results = results
        persist_local_store()
        st.success("✅ Pipeline completed!")
        st.rerun()

    # Show previous results
    if st.session_state.get("results"):
        st.markdown("## Results")
        for res in st.session_state.results:
            with st.expander(f"{'✅' if res.get('success') else '❌'} {res.get('filename')}"):
                st.write("Type:", res.get("dataset_type"))
                st.write("Issues:", len(res.get("issues", [])))

# ====================== SIDEBAR & ROUTING ======================
with st.sidebar:
    st.markdown("**🎓 Student Data Review System**")
    pages = ["Upload & Review", "Dashboard", "Cleaned Files", "About System"]
    page = st.radio("Navigation", pages, index=pages.index(st.session_state.last_page))
    st.session_state.last_page = page

    if st.button("Clear All Data"):
        st.session_state.results = []
        st.session_state.history = []
        persist_local_store()
        st.rerun()

if page == "Upload & Review":
    render_upload_and_review()
elif page == "Dashboard":
    render_dashboard(st.session_state.results)
elif page == "Cleaned Files":
    st.write("Cleaned Files page - coming soon")
else:
    st.write("About System")

persist_local_store()
st.caption("Built with Streamlit")
