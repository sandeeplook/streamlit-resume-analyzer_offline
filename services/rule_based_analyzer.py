"""
Rule-based resume verification & JD match analyzer.

Runs entirely offline using regex/keyword pattern matching — no external API,
no AI model, no network call. This trades reasoning depth for zero cost and
zero dependency on any third-party service.

The output dict intentionally matches the same schema the rest of the app
(report_export.py, app.py) expects, so no other files needed to change shape.
"""
import re
from collections import Counter
from datetime import datetime

from services.skills_data import CERTIFICATION_KEYWORDS, DEGREE_KEYWORDS, SKILLS, STOPWORDS

CURRENT_YEAR = datetime.now().year

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_RANGE_RE = re.compile(
    rf"(?:{_MONTH}\.?\s+)?((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*"
    rf"(?:{_MONTH}\.?\s+)?((?:19|20)\d{{2}}|present|current)",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{8,}\d)")
_REQUIRED_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[-•*▪‣·]\s*|^\s*\d+[.)]\s*")


def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    """Word-boundary-safe substring check (avoids 'ME' matching inside 'Acme')."""
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword.strip().lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text_lower) is not None


def _find_skills(text: str) -> list:
    found = []
    lower = text.lower()
    for skill in SKILLS:
        if _keyword_in_text(skill, lower):
            found.append(skill)
    return found


def _find_certifications(text: str) -> list:
    found = []
    lower = text.lower()
    for cert in CERTIFICATION_KEYWORDS:
        if _keyword_in_text(cert, lower):
            found.append(cert)
    return found


def _find_education(text: str) -> list:
    results = []
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        stripped_lower = stripped.lower()
        for degree in DEGREE_KEYWORDS:
            if _keyword_in_text(degree, stripped_lower):
                year_match = _YEAR_RE.search(stripped)
                year = year_match.group(0) if year_match else None
                institution = None
                for sep in [",", " - ", " – ", "|"]:
                    if sep in stripped:
                        parts = [p.strip() for p in stripped.split(sep) if p.strip()]
                        institution_candidates = [
                            p for p in parts if degree.lower() not in p.lower()
                        ]
                        if institution_candidates:
                            institution = institution_candidates[0][:80]
                        break
                results.append(
                    {"degree": stripped[:100], "institution": institution, "year": year}
                )
                break
    # de-duplicate near-identical entries
    seen = set()
    unique = []
    for r in results:
        key = r["degree"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:6]


def _find_date_ranges(text: str):
    """Return list of (start_year, end_year) tuples found in the text."""
    ranges = []
    for m in _DATE_RANGE_RE.finditer(text):
        start = int(m.group(1))
        end_raw = m.group(2).lower()
        end = CURRENT_YEAR if end_raw in ("present", "current") else int(end_raw)
        if 1950 <= start <= CURRENT_YEAR and start <= end <= CURRENT_YEAR:
            ranges.append((start, end))
    return ranges


def _ranges_overlap(ranges) -> bool:
    sorted_ranges = sorted(ranges)
    for i in range(1, len(sorted_ranges)):
        prev_end = sorted_ranges[i - 1][1]
        cur_start = sorted_ranges[i][0]
        if cur_start < prev_end:
            return True
    return False


def _estimate_total_years(ranges) -> int:
    if not ranges:
        return 0
    start = min(r[0] for r in ranges)
    end = max(r[1] for r in ranges)
    return max(0, end - start)


def _extract_experience_entries(text: str) -> list:
    lines = [l.rstrip() for l in text.splitlines()]
    entries = []
    date_line_indices = [i for i, l in enumerate(lines) if _DATE_RANGE_RE.search(l)]

    for idx, i in enumerate(date_line_indices):
        line = lines[i].strip()
        date_match = _DATE_RANGE_RE.search(line)
        duration = date_match.group(0) if date_match else None

        # Title line: text before the date on the same line, else previous
        # non-empty line.
        title_part = line[: date_match.start()].strip(" -–|,") if date_match else ""
        if not title_part:
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            title_part = lines[j].strip() if j >= 0 else "Role"

        title, company = title_part, None
        for sep in [" at ", " - ", " | ", ","]:
            if sep in title_part:
                parts = [p.strip() for p in title_part.split(sep, 1)]
                if len(parts) == 2 and parts[0] and parts[1]:
                    title, company = parts
                    break

        # Highlights: lines after this one, up to the next date-line or a
        # blank gap of 2+ lines, up to 6 bullets.
        next_boundary = date_line_indices[idx + 1] if idx + 1 < len(date_line_indices) else len(lines)
        highlights = []
        for k in range(i + 1, min(next_boundary, i + 40)):
            l = lines[k].strip()
            if not l:
                # A blank line marks the end of this job's bullet block —
                # stop here rather than bleeding into the next section.
                if highlights:
                    break
                continue
            if len(l) > 220:
                continue
            highlights.append(_BULLET_RE.sub("", l).strip())
            if len(highlights) >= 6:
                break

        entries.append(
            {
                "title": title[:100] or "Role",
                "company": company[:100] if company else None,
                "duration": duration,
                "highlights": highlights,
            }
        )

    return entries[:8]


def _extract_contact_info(text: str) -> dict:
    email = _EMAIL_RE.search(text)
    phone = _PHONE_RE.search(text)
    return {"email": email.group(0) if email else None, "phone": phone.group(0) if phone else None}


def _guess_name_and_headline(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name, headline = None, None
    if lines:
        first = lines[0]
        if (
            0 < len(first.split()) <= 5
            and "@" not in first
            and not any(ch.isdigit() for ch in first)
            and len(first) < 60
        ):
            name = first
    if len(lines) > 1:
        second = lines[1]
        if "@" not in second and len(second) < 80 and not _PHONE_RE.search(second):
            headline = second
    return name, headline


def _extract_jd_requirement_lines(jd_text: str) -> list:
    lines = [l.strip() for l in jd_text.splitlines() if l.strip()]
    bullets = [l for l in lines if _BULLET_RE.match(l)]
    if bullets:
        return [_BULLET_RE.sub("", b).strip() for b in bullets][:25]
    # fall back to splitting on sentences
    sentences = re.split(r"(?<=[.!?])\s+", jd_text)
    return [s.strip() for s in sentences if 15 < len(s.strip()) < 200][:25]


def _extract_keywords(text: str, min_len: int = 4, top_n: int = 40) -> list:
    words = re.findall(r"[A-Za-z][A-Za-z+.#/-]{" + str(min_len - 1) + r",}", text)
    counts = Counter(
        w.strip(".,") for w in words if w.lower() not in STOPWORDS and len(w) >= min_len
    )
    return [w for w, _ in counts.most_common(top_n)]


def _required_years_from_jd(jd_text: str):
    match = _REQUIRED_YEARS_RE.search(jd_text)
    return int(match.group(1)) if match else None


def analyze_resume(resume_text: str, job_description: str) -> dict:
    resume_lower = resume_text.lower()

    resume_skills = _find_skills(resume_text)
    jd_skills = _find_skills(job_description)
    matched_skills = [s for s in jd_skills if s in resume_skills]
    missing_skills = [s for s in jd_skills if s not in resume_skills]

    resume_certs = _find_certifications(resume_text)
    jd_certs = _find_certifications(job_description)

    education = _find_education(resume_text)
    date_ranges = _find_date_ranges(resume_text)
    total_years = _estimate_total_years(date_ranges)
    experience = _extract_experience_entries(resume_text)
    contact = _extract_contact_info(resume_text)
    name, headline = _guess_name_and_headline(resume_text)

    jd_keywords = _extract_keywords(job_description, min_len=5, top_n=30)
    missing_keywords = [k for k in jd_keywords if k.lower() not in resume_lower][:20]

    jd_requirements = _extract_jd_requirement_lines(job_description)
    aligned_requirements = [
        r for r in jd_requirements
        if any(s.lower() in r.lower() for s in matched_skills)
    ][:15]
    unmet_requirements = [
        r for r in jd_requirements
        if r not in aligned_requirements and not any(s.lower() in r.lower() for s in resume_skills)
    ][:15]
    partially_met_requirements = [
        r for r in jd_requirements if r not in aligned_requirements and r not in unmet_requirements
    ][:10]

    # --- Scoring ---
    skills_match = round(len(matched_skills) / len(jd_skills) * 100) if jd_skills else 60

    required_years = _required_years_from_jd(job_description)
    if required_years:
        experience_match = min(100, round((total_years / required_years) * 100)) if required_years > 0 else 60
    else:
        experience_match = 70 if experience else 30

    jd_mentions_degree = any(d.lower() in job_description.lower() for d in DEGREE_KEYWORDS)
    if jd_mentions_degree:
        education_match = 90 if education else 40
    else:
        education_match = 75 if education else 60

    if jd_certs:
        matched_certs = [c for c in jd_certs if c in resume_certs]
        certifications_match = round(len(matched_certs) / len(jd_certs) * 100)
    else:
        certifications_match = 70 if resume_certs else 55

    overall_score = round(
        skills_match * 0.40
        + experience_match * 0.30
        + education_match * 0.15
        + certifications_match * 0.15
    )
    overall_score = max(0, min(100, overall_score))

    # --- Verification / red flags ---
    red_flags = []
    if _ranges_overlap(date_ranges):
        red_flags.append("Overlapping employment date ranges were detected — worth clarifying with the candidate.")
    if not date_ranges:
        red_flags.append("No clear employment date ranges were found in the resume text.")
    if not contact["email"] and not contact["phone"]:
        red_flags.append("No email or phone contact information was found.")
    word_count = len(resume_text.split())
    if word_count < 120:
        red_flags.append("Resume text is unusually short — content may be incomplete or extraction may have missed sections.")

    is_consistent = len(red_flags) == 0

    if word_count < 150:
        formatting_quality = "Resume content is brief; limited structure could be assessed."
    elif len(experience) == 0:
        formatting_quality = "No clearly delimited work-experience entries with dates were detected."
    else:
        formatting_quality = f"Resume contains {len(experience)} identifiable experience entr{'y' if len(experience)==1 else 'ies'} and {word_count} words; structure appears parseable."

    completeness_parts = []
    completeness_parts.append("skills section: found" if resume_skills else "skills section: not clearly identified")
    completeness_parts.append("experience section: found" if experience else "experience section: not clearly identified")
    completeness_parts.append("education section: found" if education else "education section: not clearly identified")
    completeness_parts.append("contact info: found" if (contact["email"] or contact["phone"]) else "contact info: missing")
    completeness_notes = "; ".join(completeness_parts) + "."

    authenticity_notes = (
        "This is an automated, offline keyword/pattern check only — it does not verify the "
        "truthfulness of any claim. It can surface structural inconsistencies (like overlapping "
        "dates) but cannot judge whether experience descriptions are accurate. For deeper "
        "verification, a human reviewer or reference check is recommended."
    )

    # --- Narrative-ish fields (templated, not AI-generated prose) ---
    summary = (
        f"Automated scan identified {len(resume_skills)} skill keyword(s), "
        f"{len(experience)} work-experience entr{'y' if len(experience)==1 else 'ies'}, "
        f"{len(education)} education entr{'y' if len(education)==1 else 'ies'}, and "
        f"{len(resume_certs)} certification keyword(s) in the resume text. "
        f"Estimated total experience span: ~{total_years} year(s)."
    )

    match_summary = (
        f"{len(matched_skills)} of {len(jd_skills)} job-description skill keyword(s) were found "
        f"in the resume ({skills_match}% skill keyword overlap)."
        if jd_skills
        else "No specific skill keywords from a known list were detected in the job description; "
        "scoring falls back to neutral defaults for the skills dimension."
    )

    strengths = [f"Resume includes the '{s}' keyword, matching a JD requirement." for s in matched_skills[:8]]
    if not strengths:
        strengths = ["No direct JD skill-keyword matches were found — see missing skills below."]

    weaknesses = [f"'{s}' appears in the job description but not in the resume." for s in missing_skills[:8]]
    if red_flags:
        weaknesses.extend(red_flags[:3])
    if not weaknesses:
        weaknesses = ["No notable gaps identified by the automated keyword scan."]

    interview_focus_areas = [
        f"Ask the candidate to describe hands-on experience with {s}, since it's required by the "
        f"role but wasn't detected in the resume text." for s in missing_skills[:6]
    ]
    if not interview_focus_areas:
        interview_focus_areas = ["Confirm depth of experience for top matched skills through scenario-based questions."]

    if overall_score >= 80:
        recommendation = "Strong Match"
    elif overall_score >= 65:
        recommendation = "Good Match"
    elif overall_score >= 50:
        recommendation = "Possible Match"
    elif overall_score >= 35:
        recommendation = "Weak Match"
    else:
        recommendation = "Not Recommended"

    recommendation_rationale = (
        f"Overall score of {overall_score}/100 is derived from a {skills_match}% skill-keyword "
        f"overlap, an estimated experience match of {experience_match}%, an education-keyword "
        f"match of {education_match}%, and a certification match of {certifications_match}%. "
        f"This is a rule-based estimate, not an AI judgment — use it as a first-pass filter."
    )

    return {
        "candidate_summary": {
            "full_name": name,
            "headline": headline,
            "total_years_experience": f"~{total_years} years (estimated)" if total_years else None,
            "summary": summary,
        },
        "extracted_skills": resume_skills,
        "experience": experience,
        "education": education,
        "certifications": resume_certs,
        "resume_verification": {
            "is_internally_consistent": is_consistent,
            "red_flags": red_flags,
            "formatting_quality": formatting_quality,
            "completeness_notes": completeness_notes,
            "authenticity_notes": authenticity_notes,
        },
        "jd_match_analysis": {
            "match_summary": match_summary,
            "aligned_requirements": aligned_requirements,
            "partially_met_requirements": partially_met_requirements,
            "unmet_requirements": unmet_requirements,
        },
        "score_breakdown": {
            "skills_match": skills_match,
            "experience_match": experience_match,
            "education_match": education_match,
            "certifications_match": certifications_match,
            "overall_score": overall_score,
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_skills": missing_skills,
        "missing_keywords": missing_keywords,
        "interview_focus_areas": interview_focus_areas,
        "hiring_recommendation": recommendation,
        "recommendation_rationale": recommendation_rationale,
    }
