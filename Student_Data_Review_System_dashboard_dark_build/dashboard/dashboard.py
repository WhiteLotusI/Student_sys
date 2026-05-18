from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import plotly.express as px
import streamlit as st

BG = "rgba(0,0,0,0)"
FONT = "#e2e8f0"
GRID = "#223246"
CARD_BORDER = "#1f3653"


def _base_layout(fig, height=320):
    fig.update_layout(
        height=height,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font_color=FONT,
        margin=dict(l=16, r=16, t=40, b=16),
        legend=dict(bgcolor=BG, font_color=FONT, orientation="v"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def _render_card(title: str, value: str, subtitle: str = "", accent: str = "#3b82f6"):
    st.markdown(
        f"""
        <div style="background:linear-gradient(180deg, rgba(8,15,27,.95), rgba(6,12,22,.98));
                    border:1px solid {CARD_BORDER}; border-radius:16px; padding:18px 18px 14px 18px;
                    min-height:110px; box-shadow:0 6px 24px rgba(0,0,0,.28);">
            <div style="font-size:.85rem;color:#93a4bd;margin-bottom:10px;">{title}</div>
            <div style="font-size:2rem; font-weight:800; color:{accent}; line-height:1.1;">{value}</div>
            <div style="font-size:.82rem;color:#7f92ad;margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _normalize(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None:
        return None
    out = df.copy()
    out.columns = out.columns.str.strip().str.lower().str.replace(" ", "_", regex=False)
    return out


def _results_lookup(results: List[Dict[str, Any]]):
    by_type = {r.get("dataset_type"): r for r in results if r.get("dataset_type")}
    profiles = _normalize(by_type.get("profiles", {}).get("cleaned_df"))
    performance = _normalize(by_type.get("performance", {}).get("cleaned_df"))
    attendance = _normalize(by_type.get("attendance", {}).get("cleaned_df"))
    return by_type, profiles, performance, attendance


def _build_zip(results: List[Dict[str, Any]]) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        summary_rows = []
        for r in results:
            dtype = r.get("dataset_type") or "unknown"
            fname = Path(r.get("filename", dtype)).stem
            cleaned = r.get("cleaned_df")
            issues = r.get("issues", [])
            if isinstance(cleaned, pd.DataFrame):
                zf.writestr(f"cleaned/{dtype}_{fname}_cleaned.csv", cleaned.to_csv(index=False))
            if issues:
                report_df = pd.DataFrame({
                    "file": [r.get("filename")] * len(issues),
                    "dataset_type": [dtype] * len(issues),
                    "issue": issues,
                })
                zf.writestr(f"reports/{dtype}_{fname}_validation_report.csv", report_df.to_csv(index=False))
            summary_rows.append({
                "file_name": r.get("filename"),
                "dataset_type": dtype,
                "rows": r.get("raw_rows", 0),
                "status": "Needs Attention" if (r.get("error") or r.get("issues")) else "Passed",
                "success": r.get("success", False),
            })
        if summary_rows:
            zf.writestr("review_summary.csv", pd.DataFrame(summary_rows).to_csv(index=False))
    mem.seek(0)
    return mem.getvalue()


def render_dashboard(results: List[Dict[str, Any]]):
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#050b16,#091225 50%,#050a14);
                    border:1px solid #173050; border-radius:18px; padding:22px 24px;
                    box-shadow:0 10px 32px rgba(0,0,0,.35); margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:start; gap:16px; flex-wrap:wrap;">
                <div>
                    <div style="font-size:2.1rem; font-weight:800; color:#f8fafc; line-height:1.1;">Student Data Review Dashboard</div>
                    <div style="margin-top:8px; color:#8fa3bf; font-size:1rem;">Review uploaded CSV files, insights, and data quality status</div>
                </div>
                <div style="background:#0a1424; border:1px solid #1f3653; color:#dbe7f4; padding:12px 14px; border-radius:14px; font-weight:600;">📅 Live Session Dashboard</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not results:
        st.info("Run the pipeline first to populate the dashboard.")
        return

    by_type, profiles_df, performance_df, attendance_df = _results_lookup(results)

    total_files = len(results)
    total_records = sum(int(r.get("raw_rows", 0) or 0) for r in results)
    types = [r.get("dataset_type") for r in results if r.get("dataset_type")]
    types_text = " · ".join(t.title() for t in dict.fromkeys(types)) if types else "—"
    passed = sum(1 for r in results if not r.get("error") and not r.get("issues"))
    attention = total_files - passed

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _render_card("Files Reviewed", str(total_files), "uploaded CSV files", "#3b82f6")
    with c2:
        _render_card("Total Records", f"{total_records:,}", "rows reviewed across files", "#22c55e")
    with c3:
        _render_card("Dataset Types Found", types_text or "—", "detected data categories", "#a855f7")
    with c4:
        _render_card("Review Status", f"{passed} Passed · {attention} Needs Attention", "quality outcome summary", "#f59e0b")

    st.markdown("### Dataset Breakdown")
    summary_rows = []
    for r in results:
        dtype = (r.get("dataset_type") or "unknown").title()
        status = "Needs Attention" if (r.get("error") or r.get("issues")) else "Passed"
        summary_rows.append({
            "File Name": r.get("filename"),
            "Dataset Type": dtype,
            "Rows": int(r.get("raw_rows", 0) or 0),
            "Status": status,
            "Cleaned File": f"cleaned_{dtype.lower()}.csv" if r.get("cleaned_df") is not None else "—",
        })
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    left, right = st.columns([3.1, 1.3])
    with right:
        st.markdown("### Review Alerts")
        alerts = []
        if profiles_df is not None and "guardian_contact" in profiles_df.columns:
            missing_contacts = profiles_df["guardian_contact"].isna().sum() + (profiles_df["guardian_contact"].astype(str).str.strip() == "").sum()
            if missing_contacts:
                alerts.append(f"{int(missing_contacts)} students have missing guardian contacts")
        if attendance_df is not None and "attendance_percent" in attendance_df.columns:
            low_att = int((pd.to_numeric(attendance_df["attendance_percent"], errors="coerce") < 75).sum())
            if low_att:
                alerts.append(f"{low_att} students have attendance below 75%")
        if performance_df is not None and "teacher_comment" in performance_df.columns:
            miss_comments = performance_df["teacher_comment"].isna().sum() + (performance_df["teacher_comment"].astype(str).str.strip() == "").sum()
            if miss_comments:
                alerts.append(f"{int(miss_comments)} performance records are missing teacher comments")
        if not alerts:
            alerts = ["No major alerts found in the reviewed files."]
        for a in alerts:
            st.markdown(
                f"<div style='background:#08111f;border:1px solid #1f3653;border-radius:14px;padding:12px 14px;margin-bottom:10px;color:#dbe7f4;'>{a}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("### Downloads")
        for r in results:
            cleaned = r.get("cleaned_df")
            if isinstance(cleaned, pd.DataFrame):
                dtype = r.get("dataset_type") or "data"
                st.download_button(
                    f"⬇ Download {dtype.title()} CSV",
                    data=cleaned.to_csv(index=False).encode(),
                    file_name=f"cleaned_{dtype}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"dash_{dtype}_{r.get('filename')}",
                )
        st.download_button(
            "⬇ Download all files as ZIP",
            data=_build_zip(results),
            file_name="student_data_review_dashboard_export.zip",
            mime="application/zip",
            use_container_width=True,
            key="all_zip_download",
        )

    with left:
        charts1 = st.columns(3)

        with charts1[0]:
            st.markdown("### Student Profile Insights")
            if profiles_df is not None and len(profiles_df):
                if "gender" in profiles_df.columns:
                    g = profiles_df["gender"].astype(str).str.strip().replace({"": "Unknown"}).fillna("Unknown")
                    g_df = g.value_counts().reset_index()
                    g_df.columns = ["Gender", "Count"]
                    fig = px.pie(g_df, names="Gender", values="Count", hole=.55,
                                 color_discrete_sequence=["#3b82f6", "#fb7185", "#94a3b8", "#22c55e"])
                    st.plotly_chart(_base_layout(fig, 300), use_container_width=True)
                if "class" in profiles_df.columns:
                    c_df = profiles_df["class"].astype(str).value_counts().sort_index().reset_index()
                    c_df.columns = ["Class", "Students"]
                    fig = px.bar(c_df, x="Class", y="Students", text="Students",
                                 color_discrete_sequence=["#3b82f6"])
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(_base_layout(fig, 300), use_container_width=True)
            else:
                st.info("Profiles dataset not available.")

        with charts1[1]:
            st.markdown("### Performance Insights")
            if performance_df is not None and len(performance_df):
                if {"subject", "total_score"}.issubset(performance_df.columns):
                    temp = performance_df.copy()
                    temp["total_score"] = pd.to_numeric(temp["total_score"], errors="coerce")
                    s_df = temp.groupby("subject", dropna=False)["total_score"].mean().dropna().round(1).reset_index()
                    s_df.columns = ["Subject", "Average Score"]
                    fig = px.bar(s_df, x="Average Score", y="Subject", orientation="h", text="Average Score",
                                 color_discrete_sequence=["#8b5cf6"])
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(_base_layout(fig, 300), use_container_width=True)
                if "result" in performance_df.columns:
                    r_df = performance_df["result"].astype(str).str.title().value_counts().reset_index()
                    r_df.columns = ["Result", "Count"]
                    fig = px.pie(r_df, names="Result", values="Count", hole=.55,
                                 color_discrete_map={"Pass": "#22c55e", "Fail": "#ef4444"})
                    st.plotly_chart(_base_layout(fig, 300), use_container_width=True)
            else:
                st.info("Performance dataset not available.")

        with charts1[2]:
            st.markdown("### Attendance Insights")
            if attendance_df is not None and len(attendance_df):
                temp = attendance_df.copy()
                if "attendance_percent" in temp.columns:
                    temp["attendance_percent"] = pd.to_numeric(temp["attendance_percent"], errors="coerce")
                if {"class", "attendance_percent"}.issubset(temp.columns):
                    a_df = temp.groupby("class", dropna=False)["attendance_percent"].mean().dropna().round(1).reset_index()
                    a_df.columns = ["Class", "Attendance Rate"]
                    fig = px.bar(a_df, x="Class", y="Attendance Rate", text="Attendance Rate",
                                 color_discrete_sequence=["#f59e0b"])
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(_base_layout(fig, 300), use_container_width=True)
                if {"student_name", "attendance_percent"}.issubset(temp.columns):
                    low_df = temp[[c for c in ["student_name", "class", "attendance_percent"] if c in temp.columns]].copy()
                    low_df = low_df.sort_values("attendance_percent").head(5)
                    low_df["attendance_percent"] = low_df["attendance_percent"].round(1)
                    st.dataframe(low_df, use_container_width=True, hide_index=True)
            else:
                st.info("Attendance dataset not available.")
