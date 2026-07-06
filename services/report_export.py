"""Builds downloadable Markdown and PDF versions of the analysis report."""
from datetime import datetime

from fpdf import FPDF


def _list_md(items, empty_text="None identified."):
    items = items or []
    if not items:
        return empty_text
    return "\n".join(f"- {i}" for i in items)


def build_markdown_report(analysis: dict, resume_filename: str, model_used: str) -> str:
    cs = analysis.get("candidate_summary", {}) or {}
    sb = analysis.get("score_breakdown", {}) or {}
    rv = analysis.get("resume_verification", {}) or {}
    jd = analysis.get("jd_match_analysis", {}) or {}

    experience_md = "\n\n".join(
        f"### {e.get('title', '')}{' — ' + e.get('company') if e.get('company') else ''}\n"
        f"{e.get('duration') or ''}\n"
        f"{_list_md(e.get('highlights'), '')}"
        for e in (analysis.get("experience") or [])
    )

    education_md = "\n".join(
        f"- {e.get('degree', '')}"
        f"{', ' + e.get('institution') if e.get('institution') else ''}"
        f"{' (' + e.get('year') + ')' if e.get('year') else ''}"
        for e in (analysis.get("education") or [])
    ) or "Not stated."

    return f"""# Resume Verification & JD Match Report

**File analyzed:** {resume_filename}
**Model used:** {model_used}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Candidate Summary

- **Name:** {cs.get('full_name') or 'Not stated'}
- **Headline:** {cs.get('headline') or 'Not stated'}
- **Experience:** {cs.get('total_years_experience') or 'Not stated'}

{cs.get('summary', '')}

## Overall Recommendation

**{analysis.get('hiring_recommendation', '')}** (Overall score: {sb.get('overall_score', 0)}/100)

{analysis.get('recommendation_rationale', '')}

## Score Breakdown

| Dimension | Score |
| --- | --- |
| Skills Match | {sb.get('skills_match', 0)}/100 |
| Experience Match | {sb.get('experience_match', 0)}/100 |
| Education Match | {sb.get('education_match', 0)}/100 |
| Certifications Match | {sb.get('certifications_match', 0)}/100 |
| **Overall** | **{sb.get('overall_score', 0)}/100** |

## Extracted Skills

{_list_md(analysis.get('extracted_skills'))}

## Experience

{experience_md or 'No experience entries found.'}

## Education

{education_md}

## Certifications

{_list_md(analysis.get('certifications'))}

## Resume Verification

- **Internally consistent:** {'Yes' if rv.get('is_internally_consistent') else 'No'}
- **Formatting quality:** {rv.get('formatting_quality', '')}
- **Completeness notes:** {rv.get('completeness_notes', '')}
- **Authenticity notes:** {rv.get('authenticity_notes', '')}

### Red Flags

{_list_md(rv.get('red_flags'), 'None identified.')}

## JD Match Analysis

{jd.get('match_summary', '')}

### Aligned Requirements
{_list_md(jd.get('aligned_requirements'))}

### Partially Met Requirements
{_list_md(jd.get('partially_met_requirements'))}

### Unmet Requirements
{_list_md(jd.get('unmet_requirements'))}

## Strengths

{_list_md(analysis.get('strengths'))}

## Weaknesses

{_list_md(analysis.get('weaknesses'))}

## Missing Skills

{_list_md(analysis.get('missing_skills'))}

## Missing Keywords

{_list_md(analysis.get('missing_keywords'))}

## Interview Focus Areas

{_list_md(analysis.get('interview_focus_areas'))}
"""


class _ReportPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _safe(text) -> str:
    """FPDF core fonts are latin-1 only; replace unsupported characters."""
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def build_pdf_report(analysis: dict, resume_filename: str, model_used: str) -> bytes:
    cs = analysis.get("candidate_summary", {}) or {}
    sb = analysis.get("score_breakdown", {}) or {}
    rv = analysis.get("resume_verification", {}) or {}
    jd = analysis.get("jd_match_analysis", {}) or {}

    pdf = _ReportPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def heading(text, size=13):
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(20, 99, 86)
        pdf.multi_cell(0, 8, _safe(text))
        pdf.ln(1)
        pdf.set_text_color(27, 36, 48)

    def paragraph(text, size=10):
        pdf.set_font("Helvetica", size=size)
        pdf.multi_cell(0, 5.5, _safe(text) or "-")
        pdf.ln(1)

    def bullets(items, empty_text="None identified."):
        items = items or []
        pdf.set_font("Helvetica", size=10)
        if not items:
            paragraph(empty_text)
            return
        for item in items:
            pdf.multi_cell(0, 5.5, _safe(f"-  {item}"))
        pdf.ln(1)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(27, 36, 48)
    pdf.multi_cell(0, 10, _safe("Resume Verification & JD Match Report"))
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(91, 100, 112)
    pdf.multi_cell(
        0,
        5,
        _safe(
            f"File: {resume_filename}  |  Model: {model_used}  |  "
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ),
    )
    pdf.ln(3)
    pdf.set_text_color(27, 36, 48)

    heading(f"Overall Score: {sb.get('overall_score', 0)}/100 — {analysis.get('hiring_recommendation', '')}")
    paragraph(analysis.get("recommendation_rationale", ""))

    heading("Candidate Summary")
    paragraph(
        f"Name: {cs.get('full_name') or 'Not stated'}   |   "
        f"Headline: {cs.get('headline') or 'Not stated'}   |   "
        f"Experience: {cs.get('total_years_experience') or 'Not stated'}"
    )
    paragraph(cs.get("summary", ""))

    heading("Score Breakdown")
    paragraph(
        f"Skills: {sb.get('skills_match', 0)}/100   "
        f"Experience: {sb.get('experience_match', 0)}/100   "
        f"Education: {sb.get('education_match', 0)}/100   "
        f"Certifications: {sb.get('certifications_match', 0)}/100"
    )

    heading("Extracted Skills")
    bullets(analysis.get("extracted_skills"))

    heading("Experience")
    experience = analysis.get("experience") or []
    if not experience:
        paragraph("No experience entries found.")
    for e in experience:
        title_line = e.get("title", "")
        if e.get("company"):
            title_line += f" — {e.get('company')}"
        if e.get("duration"):
            title_line += f" ({e.get('duration')})"
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, _safe(title_line))
        bullets(e.get("highlights"), "")

    heading("Education")
    education = analysis.get("education") or []
    bullets(
        [
            f"{e.get('degree', '')}"
            f"{', ' + e.get('institution') if e.get('institution') else ''}"
            f"{' (' + e.get('year') + ')' if e.get('year') else ''}"
            for e in education
        ],
        "Not stated.",
    )

    heading("Certifications")
    bullets(analysis.get("certifications"), "No certifications listed.")

    heading("Resume Verification")
    paragraph(f"Internally consistent: {'Yes' if rv.get('is_internally_consistent') else 'No'}")
    paragraph(f"Formatting quality: {rv.get('formatting_quality', '')}")
    paragraph(f"Completeness notes: {rv.get('completeness_notes', '')}")
    paragraph(f"Authenticity notes: {rv.get('authenticity_notes', '')}")
    paragraph("Red flags:")
    bullets(rv.get("red_flags"))

    heading("JD Match Analysis")
    paragraph(jd.get("match_summary", ""))
    paragraph("Aligned requirements:")
    bullets(jd.get("aligned_requirements"))
    paragraph("Partially met requirements:")
    bullets(jd.get("partially_met_requirements"))
    paragraph("Unmet requirements:")
    bullets(jd.get("unmet_requirements"), "None — strong coverage.")

    heading("Strengths")
    bullets(analysis.get("strengths"))

    heading("Weaknesses")
    bullets(analysis.get("weaknesses"))

    heading("Missing Skills")
    bullets(analysis.get("missing_skills"), "None — all required skills present.")

    heading("Missing Keywords")
    bullets(analysis.get("missing_keywords"), "None — strong keyword coverage.")

    heading("Interview Focus Areas")
    bullets(analysis.get("interview_focus_areas"))

    return bytes(pdf.output())
