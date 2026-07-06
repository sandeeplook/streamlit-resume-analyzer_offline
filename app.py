"""
AI Resume Verification & JD Match Analyzer — Streamlit edition (offline).

Single-process app: the UI, file handling, text extraction, and the
rule-based analysis all run inside this one Streamlit script. No database,
no login, no external API calls — everything happens locally in memory for
the current session only.
"""
import streamlit as st

from config import get_settings
from services.rule_based_analyzer import analyze_resume
from services.exceptions import AppError
from services.report_export import build_markdown_report, build_pdf_report
from services.text_extraction import extract_resume_text

st.set_page_config(
    page_title="AI Resume Verification & JD Match Analyzer",
    page_icon="🔎",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Styling — a light, "verification report" look, distinct from Streamlit's
# stock theme.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #EEF0EC; }
    .block-container { max-width: 880px; padding-top: 2.5rem; }
    h1, h2, h3 { font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.01em; }
    .tagline {
        font-family: 'Courier New', monospace; font-size: 12px; color: #5B6470;
        text-transform: uppercase; letter-spacing: 0.06em; margin-top: -8px;
    }
    .seal-badge {
        display: inline-block; border: 3px double #146356; border-radius: 50%;
        width: 118px; height: 118px; text-align: center; line-height: 1.1;
        padding-top: 30px; background: #E3EDE9; font-family: 'Courier New', monospace;
    }
    .seal-score { font-size: 30px; font-weight: 700; color: #146356; }
    .seal-sub { font-size: 10px; color: #5B6470; text-transform: uppercase; }
    .pill {
        display: inline-block; font-family: 'Courier New', monospace; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.06em; padding: 4px 10px;
        border-radius: 999px; background: #1B2430; color: #EEF0EC;
    }
    .flag { color: #A63D40; }
    .missing-tag {
        display: inline-block; font-family: 'Courier New', monospace; font-size: 12px;
        padding: 3px 9px; border-radius: 999px; border: 1px solid #A63D40;
        color: #A63D40; background: #F3E1E0; margin: 2px;
    }
    .skill-tag {
        display: inline-block; font-family: 'Courier New', monospace; font-size: 12px;
        padding: 3px 9px; border-radius: 999px; border: 1px solid #D9DCD4;
        background: #FFFFFF; margin: 2px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = None  # holds dict: analysis, filename, model
if "error_message" not in st.session_state:
    st.session_state.error_message = None


def reset_state():
    st.session_state.analysis_data = None
    st.session_state.error_message = None


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("🔎 **VERIFY**")
st.title("AI Resume Verification & JD Match Analyzer")
st.markdown('<div class="tagline">no database · no login · in-memory only</div>', unsafe_allow_html=True)
st.write("")

settings = get_settings()
st.info(
    "Runs fully offline — resume parsing and JD matching use local keyword/pattern "
    "rules only. No external API, no account, no cost.",
    icon="🔒",
)

# ---------------------------------------------------------------------------
# Stage 1 & 2: Upload + JD input, then run analysis (progress shown inline)
# ---------------------------------------------------------------------------
if st.session_state.analysis_data is None:
    st.subheader("Verify a candidate against a role")
    st.caption(
        "Upload a resume and provide the job description. A local rule-based engine "
        "extracts skills, checks consistency, and scores the fit against the role — "
        "no data leaves this app."
    )

    if st.session_state.error_message:
        st.error(st.session_state.error_message)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**01 — Resume**")
        resume_file = st.file_uploader(
            "Upload resume (PDF or DOCX, up to 10MB)",
            type=["pdf", "docx"],
            key="resume_uploader",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown("**02 — Job Description**")
        jd_tab_paste, jd_tab_file = st.tabs(["Paste text", "Upload .txt"])
        jd_text_paste = jd_tab_paste.text_area(
            "Paste the full job description",
            height=220,
            label_visibility="collapsed",
            placeholder="Paste the full job description here…",
        )
        jd_file = jd_tab_file.file_uploader(
            "Upload a .txt job description", type=["txt"], label_visibility="collapsed"
        )

    job_description = jd_text_paste
    if jd_file is not None:
        job_description = jd_file.read().decode("utf-8", errors="ignore")

    st.write("")
    run_clicked = st.button("Run analysis →", type="primary", use_container_width=False)

    if run_clicked:
        st.session_state.error_message = None

        if resume_file is None:
            st.session_state.error_message = "Please upload a resume file."
            st.rerun()
        elif not job_description or len(job_description.strip()) <= 20:
            st.session_state.error_message = (
                "Please provide a more complete job description (at least a few sentences)."
            )
            st.rerun()
        else:
            file_bytes = resume_file.getvalue()
            if len(file_bytes) > settings.max_upload_size_bytes:
                st.session_state.error_message = (
                    f"Resume file exceeds the {settings.max_upload_size_mb}MB size limit."
                )
                st.rerun()

            progress_box = st.status("Analyzing candidate fit…", expanded=True)
            try:
                progress_box.write("Extracting text from resume…")
                resume_text = extract_resume_text(resume_file.name, file_bytes)

                progress_box.write("Reading job description…")
                jd_clean = job_description.strip()

                progress_box.write("Cross-checking consistency and scoring match…")
                analysis = analyze_resume(resume_text, jd_clean)

                progress_box.update(label="Analysis complete", state="complete", expanded=False)

                st.session_state.analysis_data = {
                    "analysis": analysis,
                    "resume_filename": resume_file.name,
                    "model_used": settings.analysis_engine_label,
                }
                st.rerun()

            except AppError as exc:
                progress_box.update(label="Analysis failed", state="error", expanded=False)
                detail = f" ({exc.details})" if exc.details else ""
                st.session_state.error_message = f"{exc.message}{detail}"
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                progress_box.update(label="Analysis failed", state="error", expanded=False)
                st.session_state.error_message = f"Unexpected error: {exc}"
                st.rerun()

# ---------------------------------------------------------------------------
# Stage 3: Results dashboard
# ---------------------------------------------------------------------------
else:
    data = st.session_state.analysis_data
    a = data["analysis"]
    cs = a.get("candidate_summary", {}) or {}
    sb = a.get("score_breakdown", {}) or {}
    rv = a.get("resume_verification", {}) or {}
    jd = a.get("jd_match_analysis", {}) or {}

    header_col1, header_col2 = st.columns([1, 3])
    with header_col1:
        st.markdown(
            f"""<div class="seal-badge">
                    <div class="seal-score">{sb.get('overall_score', 0)}</div>
                    <div class="seal-sub">/ 100</div>
                </div>""",
            unsafe_allow_html=True,
        )
    with header_col2:
        st.markdown(f"### {cs.get('full_name') or 'Candidate'}")
        st.caption(
            f"{cs.get('headline') or 'Role unspecified'} · "
            f"{cs.get('total_years_experience') or 'Experience not stated'}"
        )
        st.markdown(f'<span class="pill">{a.get("hiring_recommendation", "")}</span>', unsafe_allow_html=True)

    st.write("")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Skills", f"{sb.get('skills_match', 0)}/100")
    sc2.metric("Experience", f"{sb.get('experience_match', 0)}/100")
    sc3.metric("Education", f"{sb.get('education_match', 0)}/100")
    sc4.metric("Certifications", f"{sb.get('certifications_match', 0)}/100")

    st.write("")
    md_report = build_markdown_report(a, data["resume_filename"], data["model_used"])
    pdf_report = build_pdf_report(a, data["resume_filename"], data["model_used"])

    dl1, dl2, dl3 = st.columns([1, 1, 2])
    dl1.download_button(
        "⬇ Download PDF report",
        data=pdf_report,
        file_name="resume-analysis.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    dl2.download_button(
        "⬇ Download Markdown report",
        data=md_report,
        file_name="resume-analysis.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.write("")

    with st.expander("Candidate Summary", expanded=True):
        st.write(cs.get("summary", ""))
        st.caption(a.get("recommendation_rationale", ""))

    with st.expander("JD Match Analysis", expanded=True):
        st.write(jd.get("match_summary", ""))
        st.markdown("**Aligned requirements**")
        for item in jd.get("aligned_requirements") or []:
            st.markdown(f"- {item}")
        st.markdown("**Partially met requirements**")
        for item in jd.get("partially_met_requirements") or []:
            st.markdown(f"- {item}")
        st.markdown("**Unmet requirements**")
        unmet = jd.get("unmet_requirements") or []
        if not unmet:
            st.caption("None — strong coverage.")
        for item in unmet:
            st.markdown(f"- {item}")

    with st.expander("Extracted Skills"):
        skills = a.get("extracted_skills") or []
        if skills:
            st.markdown(
                "".join(f'<span class="skill-tag">{s}</span>' for s in skills),
                unsafe_allow_html=True,
            )
        else:
            st.caption("No skills extracted.")

    with st.expander("Experience"):
        experience = a.get("experience") or []
        if not experience:
            st.caption("No experience entries found.")
        for e in experience:
            title_line = e.get("title", "")
            if e.get("company"):
                title_line += f" — {e.get('company')}"
            st.markdown(f"**{title_line}**")
            st.caption(e.get("duration") or "Duration not stated")
            for h in e.get("highlights") or []:
                st.markdown(f"- {h}")
            st.divider()

    with st.expander("Education"):
        education = a.get("education") or []
        if not education:
            st.caption("No education entries found.")
        for e in education:
            st.markdown(f"**{e.get('degree', '')}**")
            meta = e.get("institution") or "Institution not stated"
            if e.get("year"):
                meta += f" · {e.get('year')}"
            st.caption(meta)

    with st.expander("Certifications"):
        certs = a.get("certifications") or []
        if certs:
            st.markdown(
                "".join(f'<span class="skill-tag">{c}</span>' for c in certs),
                unsafe_allow_html=True,
            )
        else:
            st.caption("No certifications listed.")

    with st.expander("Resume Verification"):
        st.write(
            f"**Internally consistent:** "
            f"{'Yes' if rv.get('is_internally_consistent') else 'No — see flags below'}"
        )
        st.write(f"**Formatting quality:** {rv.get('formatting_quality', '')}")
        st.write(f"**Completeness:** {rv.get('completeness_notes', '')}")
        st.write(f"**Authenticity notes:** {rv.get('authenticity_notes', '')}")
        st.markdown("**Red flags**")
        flags = rv.get("red_flags") or []
        if not flags:
            st.caption("None identified.")
        for f in flags:
            st.markdown(f'- <span class="flag">{f}</span>', unsafe_allow_html=True)

    with st.expander("Strengths & Weaknesses"):
        st.markdown("**Strengths**")
        for s in a.get("strengths") or []:
            st.markdown(f"- {s}")
        st.markdown("**Weaknesses**")
        for w in a.get("weaknesses") or []:
            st.markdown(f"- {w}")

    with st.expander("Missing Skills & Keywords"):
        st.markdown("**Missing skills**")
        missing_skills = a.get("missing_skills") or []
        if missing_skills:
            st.markdown(
                "".join(f'<span class="missing-tag">{s}</span>' for s in missing_skills),
                unsafe_allow_html=True,
            )
        else:
            st.caption("None — all required skills present.")
        st.markdown("**Missing keywords**")
        missing_kw = a.get("missing_keywords") or []
        if missing_kw:
            st.markdown(
                "".join(f'<span class="missing-tag">{s}</span>' for s in missing_kw),
                unsafe_allow_html=True,
            )
        else:
            st.caption("None — strong keyword coverage.")

    with st.expander("Interview Focus Areas"):
        for item in a.get("interview_focus_areas") or []:
            st.markdown(f"- {item}")

    st.write("")
    st.button("← Analyze another candidate", on_click=reset_state)

st.write("")
st.caption(
    "Analysis generated by an offline rule-based engine · Not a substitute for "
    "independent background verification or professional judgment."
)
