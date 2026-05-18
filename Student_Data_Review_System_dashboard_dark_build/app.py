"""
Student Data Review System — Streamlit App
Fixed: Persistence + JSON Serialization
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
st.set_page_config(
    page_title="Student Data Review System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: radial-gradient(circle at top left, #071120 0%, #040a14 45%, #02060d 100%); color: #eef4ff; }
</style>
""",
    unsafe_allow_html=True,
)


# ====================== PERSISTENCE (FIXED) ======================
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

def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)

def _snapshot_dataframe(df, persist_id: str, suffix: str):
    if not isinstance(df, pd.DataFrame): return None
    path = SNAPSHOT_DIR / f"{persist_id}_{suffix}.csv"
    df.to_csv(path, index=False)
    return str(path.relative_to(ROOT))

def _serialize_results(results):
    serialized = []
    for r in results or []:
        persist_id = r.get("persist_id") or _safe_name(r.get("filename", "file"))
        raw_snap = r.get("raw_snapshot") or _snapshot_dataframe(r.get("raw_df"), persist_id, "raw")
        clean_snap = r.get("cleaned_snapshot") or _snapshot_dataframe(r.get("cleaned_df"), persist_id, "cleaned")
        
        item = {k: v for k, v in r.items() if k not in ["raw_df", "cleaned_df"]}
        item["raw_snapshot"] = raw_snap
        item["cleaned_snapshot"] = clean_snap
        serialized.append(item)
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
        _write_json(LOCAL_STATE_FILE, payload)
        if results:
            _write_json(LATEST_REVIEW_FILE, {"results": _serialize_results(results)})
    except Exception as e:
        st.warning(f"Local activity memory could not be saved: {e}")

def restore_local_store_into_session():
    review = _load_latest_review()
    store = _load_local_store()
    
    if review.get("results"):
        st.session_state.results = review["results"]
    elif store.get("results"):
        st.session_state.results = store["results"]

    if store.get("history"):
        st.session_state.history = store.get("history", [])
    if store.get("last_page"):
        st.session_state.last_page = store.get("last_page", "Upload & Review")


# ====================== SESSION STATE ======================
if "results" not in st.session_state:
    st.session_state.results = []
if "history" not in st.session_state:
    st.session_state.history = []
if "last_page" not in st.session_state:
    st.session_state.last_page = "Upload & Review"

restore_local_store_into_session()


# ====================== ORIGINAL PIPELINE CODE ======================
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
        raise ValueError(f"No dataset type matched well enough (best score {best_score:.0%}).")
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
        res["raw_df"] = raw_df.copy()
        res["raw_rows"] = len(raw_df)
    except Exception as e:
        res["error"] = f"Could not read CSV: {e}"
        return res

    norm_df = raw_df.copy()
    norm_df.columns = norm_df.columns.str.strip().str.lower().str.replace(" ", "_")

    try:
        dtype, score = fuzzy_classify(norm_df)
        res["dataset_type"] = dtype
        res["match_score"] = score
    except Exception as e:
        res["error"] = str(e)
        return res

    try:
        res["issues"] = VALIDATE_FN[dtype](norm_df)
    except Exception as e:
        res["issues"] = [f"Validator error: {e}"]

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
def render_review_results(results):
    if not results:
        return
    st.markdown("## Results")
    for res in results:
        with st.expander(f"{'✅' if res.get('success') else '❌'} {res.get('filename')}", expanded=True):
            st.write("**Dataset Type:**", res.get("dataset_type"))
            st.write("**Match Score:**", f"{res.get('match_score', 0):.0%}")
            if res.get("issues"):
                st.write("**Issues:**", res.get("issues"))
            if res.get("cleaned_df") is not None:
                st.download_button("Download Cleaned CSV", 
                                 data=res["cleaned_df"].to_csv(index=False).encode(),
                                 file_name=f"cleaned_{res.get('dataset_type')}.csv")


def render_upload_and_review():
    st.markdown("### Upload & Review")
    uploaded_files = st.file_uploader("Drop your CSV files here", type=["csv"], accept_multiple_files=True)

    if uploaded_files and st.button("🚀 Run Pipeline", type="primary"):
        results = []
        for f in uploaded_files:
            r = run_pipeline(f)
            results.append(r)
            st.session_state.history.append({
                "timestamp": r["timestamp"],
                "filename": r["filename"],
                "success": r["success"]
            })
        st.session_state.results = results
        persist_local_store()
        st.success("Pipeline completed!")

    render_review_results(st.session_state.get("results", []))


# ====================== SIDEBAR ======================
with st.sidebar:
    st.markdown("**🎓 Student Data Review System**")
    pages = ["Upload & Review", "Dashboard", "Cleaned Files", "About System"]
    page = st.radio("Go to", pages, index=pages.index(st.session_state.last_page))
    st.session_state.last_page = page

    if st.button("Clear saved local activity"):
        st.session_state.results = []
        st.session_state.history = []
        persist_local_store()
        st.rerun()

# ====================== PAGE ROUTING ======================
if page == "Upload & Review":
    render_upload_and_review()
elif page == "Dashboard":
    render_dashboard(st.session_state.results)
elif page == "Cleaned Files":
    st.markdown("### Cleaned Files")
    for r in st.session_state.get("results", []):
        if r.get("cleaned_df") is not None:
            st.download_button(f"Download {r.get('dataset_type')}", 
                             data=r["cleaned_df"].to_csv(index=False).encode(),
                             file_name=f"cleaned_{r.get('dataset_type')}.csv")
else:
    st.markdown("### About System")
    st.info("Student Data Review System v1.0")

persist_local_store()
st.caption("Student Data Review System · Built with Streamlit")
