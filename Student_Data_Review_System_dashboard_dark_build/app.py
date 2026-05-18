"""
Student Data Review System — Streamlit App
Fixed Version - Persistent across pages
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
for d in (ROOT / "data" / "raw", ROOT / "data" / "cleaned", 
          ROOT / "scripts" / "logs", ROOT / "data" / "local_store"):
    d.mkdir(parents=True, exist_ok=True)

RAW_DIR = ROOT / "data" / "raw"
LOCAL_STORE_DIR = ROOT / "data" / "local_store"
SNAPSHOT_DIR = LOCAL_STORE_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_STATE_FILE = LOCAL_STORE_DIR / "app_state.json"
LATEST_REVIEW_FILE = LOCAL_STORE_DIR / "latest_review.json"

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Student Data Review System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ====================== CSS ======================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.stApp { background: radial-gradient(circle at top left, #071120 0%, #040a14 45%, #02060d 100%); color: #eef4ff; }
</style>
""",
    unsafe_allow_html=True,
)

# ====================== PERSISTENCE FUNCTIONS ======================
def _safe_name(value: str) -> str:
    text = str(value or "item").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:80] or "item"

def _load_local_store():
    if not LOCAL_STATE_FILE.exists():
        return {}
    try:
        with open(LOCAL_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _load_latest_review():
    if not LATEST_REVIEW_FILE.exists():
        return {}
    try:
        with open(LATEST_REVIEW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _write_json_file(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)

def _restore_dataframe(rel_path):
    if not rel_path:
        return None
    try:
        return pd.read_csv(ROOT / rel_path)
    except:
        return None

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
    if not isinstance(df, pd.DataFrame):
        return None
    path = SNAPSHOT_DIR / f"{persist_id}_{suffix}.csv"
    df.to_csv(path, index=False)
    return str(path.relative_to(ROOT))

def _serialize_results(results):
    serialized = []
    for idx, r in enumerate(results or []):
        persist_id = r.get("persist_id") or _safe_name(f"{idx}_{r.get('dataset_type')}_{r.get('filename')}")
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
    except Exception as e:
        st.warning(f"Save failed: {e}")

def restore_local_store_into_session():
    """Force restore every time"""
    review = _load_latest_review()
    store = _load_local_store()

    if review.get("results"):
        st.session_state.results = _restore_results(review["results"])
    elif store.get("results"):
        st.session_state.results = _restore_results(store["results"])

    if store.get("history"):
        st.session_state.history = store.get("history", [])
    if store.get("last_page"):
        st.session_state.last_page = store.get("last_page", "Upload & Review")

# ====================== INITIALIZE & RESTORE ======================
if "results" not in st.session_state:
    st.session_state.results = []
if "history" not in st.session_state:
    st.session_state.history = []
if "last_page" not in st.session_state:
    st.session_state.last_page = "Upload & Review"

restore_local_store_into_session()

# ====================== PIPELINE FUNCTIONS ======================
# (Same as before - shortened for brevity)
EXPECTED = { ... }  # Keep your original EXPECTED dict here
BADGE_HTML = { ... } # Keep your original BADGE_HTML

# ... Include all your functions: fuzzy_classify, run_pipeline, capture_clean, etc.
# I'll assume you keep the rest from previous version. 

# For now, main structure:
def render_upload_and_review():
    # Your upload logic here...
    uploaded_files = st.file_uploader("Drop your CSV files here", type=["csv"], accept_multiple_files=True)
    
    if uploaded_files and st.button("🚀 Run Pipeline", type="primary"):
        results = []
        for f in uploaded_files:
            r = run_pipeline(f)
            results.append(r)
            st.session_state.history.append({
                "timestamp": r["timestamp"],
                "filename": r["filename"],
                "dataset_type": r.get("dataset_type"),
                "success": r.get("success", False)
            })
        st.session_state.results = results
        persist_local_store()
        st.success("Processing completed!")
        st.rerun()

    # Show results even if no new upload
    if st.session_state.results:
        st.markdown("## Results")
        for res in st.session_state.results:
            st.write(res.get("filename"), res.get("dataset_type"))

# ====================== SIDEBAR ======================
with st.sidebar:
    st.markdown("**Student Data Review System**")
    pages = ["Upload & Review", "Dashboard", "Cleaned Files", "About System"]
    page = st.radio("Go to", pages, index=pages.index(st.session_state.last_page))
    st.session_state.last_page = page

    if st.button("Clear All Data"):
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
    st.write("Cleaned Files Page")
else:
    st.write("About System")

persist_local_store()
st.caption("Student Data Review System")
