"""
Rule-based resume verification & JD match analyzer.

Runs entirely offline using regex/keyword pattern matching plus lightweight
fuzzy matching (stdlib difflib only) — no external API, no AI model, no
network call. This trades reasoning depth for zero cost and zero dependency
on any third-party service.

Improvements over the basic version:
- Section-aware parsing: resume text is split into Skills/Experience/
  Education/Certifications blocks (when headers are detected) so extraction
  is scoped to the right part of the document instead of scanning everything
  as one blob.
- Synonym/alias matching (services/skills_data.SKILL_SYNONYMS) so "ML",
  "JS", "K8s" etc. count as their canonical skill.
- Fuzzy matching (difflib) on tokens found in a detected Skills section, to
  catch minor typos/spacing variants that exact matching would miss.
- JD "must-have" vs "nice-to-have" section splitting, so missing mandatory
  skills are weighted more heavily than missing optional ones.

The output dict intentionally matches the same schema the rest of the app
(report_export.py, app.py) expects, so no other files needed to change shape.
"""
import difflib
import re
from collections import Counter
from datetime import datetime

from services.skills_data import (
    CERTIFICATION_KEYWORDS,
    DEGREE_KEYWORDS,
    JD_MUST_HAVE_HEADERS,
    JD_NICE_TO_HAVE_HEADERS,
    SECTION_HEADERS,
    SKILL_SYNONYMS,
    SKILLS,
    STOPWORDS,
)

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
_HEADER_STRIP_RE = re.compile(r"[^a-z0-9& ]+")


# ---------------------------------------------------------------------------
# Section-aware parsing
# ---------------------------------------------------------------------------
def _normalize_header(line: str) -> str:
    return _HEADER_STRIP_RE.sub("", line.strip().lower()).strip()


def _split_into_sections(text: str) -> dict:
    """
    Scan lines for known section header phrases and return
    {section_key: "joined body text"} for whichever sections were found.
    Header lines themselves are excluded from the body text.
    """
    lines = text.splitlines()
    header_hits = []  # (line_index, section_key)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 45:
            continue
        normalized = _normalize_header(stripped)
        if not normalized:
            continue
        for section_key, phrases in SECTION_HEADERS.items():
            if normalized in phrases:
                header_hits.append((i, section_key))
                break

    sections = {}
    for idx, (line_no, key) in enumerate(header_hits):
        start = line_no + 1
        end = header_hits[idx + 1][0] if idx + 1 < len(header_hits) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        # Later same-name headers extend rather than overwrite.
        sections[key] = (sections.get(key, "") + "\n" + body).strip() if key in sections else body

    return sections


def _split_jd_sections(jd_text: str):
    """Return (must_have_text, nice_to_have_text). Falls back to
    (full_text, "") if no explicit headers are found."""
    lines = jd_text.splitlines()
    hits = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        normalized = _normalize_header(stripped)
        if not normalized:
            continue
        if normalized in JD_MUST_HAVE_HEADERS:
            hits.append((i, "must"))
        elif normalized in JD_NICE_TO_HAVE_HEADERS:
            hits.append((i, "nice"))

    if not hits:
        return jd_text, ""

    must_parts, nice_parts = [], []
    for idx, (line_no, kind) in enumerate(hits):
        start = line_no + 1
        end = hits[idx + 1][0] if idx + 1 < len(hits) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        (must_parts if kind == "must" else nice_parts).append(body)

    return "\n".join(must_parts).strip(), "\n".join(nice_parts).strip()


# ---------------------------------------------------------------------------
# Keyword / fuzzy matching helpers
# ---------------------------------------------------------------------------
def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    """Word-boundary-safe substring check (avoids 'ME' matching inside 'Acme')."""
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword.strip().lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text_lower) is not None


def _find_skills_exact(text: str) -> list:
    lower = text.lower()
    return [skill for skill in SKILLS if _keyword_in_text(skill, lower)]


def _find_skills_via_synonyms(text: str) -> list:
    lower = text.lower()
    found = []
    for alias, canonical in SKILL_SYNONYMS.items():
        if _keyword_in_text(alias, lower):
            found.append(canonical)
    return found


def _fuzzy_match_tokens_to_skills(tokens: list, cutoff: float = 0.84) -> list:
    """Catch minor typos/variants (e.g. 'Djnago', 'Postgre SQL') among tokens
    pulled from a resume's dedicated Skills section."""
    skills_lower = {s.lower(): s for s in SKILLS}
    found = []
    for token in tokens:
        cleaned = token.strip(" .-|/").lower()
        if len(cleaned) < 3:
            continue
        if cleaned in skills_lower:
            found.append(skills_lower[cleaned])
            continue
        match = difflib.get_close_matches(cleaned, skills_lower.keys(), n=1, cutoff=cutoff)
        if match:
            found.append(skills_lower[match[0]])
    return found


def _find_skills(text: str, skills_section_text: str = "") -> list:
    """Combine exact matching, synonym matching, and (when a Skills section
    was identified) fuzzy matching, deduped and in a stable order."""
    found = list(dict.fromkeys(_find_skills_exact(text) + _find_skills_via_synonyms(text)))
    if skills_section_text:
        tokens = re.split(r"[,\n•;|/]+", skills_section_text)
        for s in _fuzzy_match_tokens_to_skills(tokens):
            if s not in found:
                found.append(s)
    return found


def _find_certifications(text: str) -> list:
    lower = text.lower()
    return [cert for cert in CERTIFICATION_KEYWORDS if _keyword_in_text(cert, lower)]


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
    seen = set()
    unique = []
    for r in results:
        key = r["degree"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:6]


def _find_date_ranges(text: str):
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

        next_boundary = date_line_indices[idx + 1] if idx + 1 < len(date_line_indices) else len(lines)
        highlights = []
        for k in range(i + 1, min(next_boundary, i + 40)):
            l = lines[k].strip()
            if not l:
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def analyze_resume(resume_text: str, job_description: str) -> dict:
    resume_lower = resume_text.lower()
    resume_sections = _split_into_sections(resume_text)

    # Scope extraction to the right section when we can identify one;
    # otherwise fall back to scanning the whole document (previous behavior).
    experience_source = resume_sections.get("experience") or resume_text
    education_source = resume_sections.get("education") or resume_text
    certifications_source = resume_sections.get("certifications") or resume_text
    skills_section_text = resume_sections.get("skills", "")

    resume_skills = _find_skills(resume_text, skills_section_text=skills_section_text)

    # --- JD: split into must-have vs nice-to-have for weighted scoring ---
    jd_must_text, jd_nice_text = _split_jd_sections(job_description)
    jd_must_skills = _find_skills(jd_must_text)
    jd_nice_skills = [s for s in _find_skills(jd_nice_text) if s not in jd_must_skills]
    jd_skills = list(dict.fromkeys(jd_must_skills + jd_nice_skills))

    matched_must = [s for s in jd_must_skills if s in resume_skills]
    missing_must = [s for s in jd_must_skills if s not in resume_skills]
    matched_nice = [s for s in jd_nice_skills if s in resume_skills]
    missing_nice = [s for s in jd_nice_skills if s not in resume_skills]

    matched_skills = list(dict.fromkeys(matched_must + matched_nice))
    missing_skills = list(dict.fromkeys(missing_must + missing_nice))

    resume_certs = _find_certifications(certifications_source)
    jd_certs = _find_certifications(job_description)

    education = _find_education(education_source)
    date_ranges = _find_date_ranges(experience_source)
    total_years = _estimate_total_years(date_ranges)
    experience = _extract_experience_entries(experience_source)
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
    if jd_must_skills or jd_nice_skills:
        must_pct = round(len(matched_must) / len(jd_must_skills) * 100) if jd_must_skills else None
        nice_pct = round(len(matched_nice) / len(jd_nice_skills) * 100) if jd_nice_skills else None
        if must_pct is not None and nice_pct is not None:
            skills_match = round(must_pct * 0.8 + nice_pct * 0.2)
        else:
            skills_match = must_pct if must_pct is not None else nice_pct
    else:
        skills_match = 60

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
        detected_sections = ", ".join(k for k in ["skills", "experience", "education", "certifications"] if k in resume_sections) or "none"
        formatting_quality = (
            f"Resume contains {len(experience)} identifiable experience entr{'y' if len(experience)==1 else 'ies'} "
            f"and {word_count} words; detected section headers: {detected_sections}."
        )

    completeness_parts = [
        "skills section: found" if resume_skills else "skills section: not clearly identified",
        "experience section: found" if experience else "experience section: not clearly identified",
        "education section: found" if education else "education section: not clearly identified",
        "contact info: found" if (contact["email"] or contact["phone"]) else "contact info: missing",
    ]
    completeness_notes = "; ".join(completeness_parts) + "."

    authenticity_notes = (
        "This is an automated, offline keyword/pattern check only — it does not verify the "
        "truthfulness of any claim. It can surface structural inconsistencies (like overlapping "
        "dates) but cannot judge whether experience descriptions are accurate. For deeper "
        "verification, a human reviewer or reference check is recommended."
    )

    summary = (
        f"Automated scan identified {len(resume_skills)} skill keyword(s), "
        f"{len(experience)} work-experience entr{'y' if len(experience)==1 else 'ies'}, "
        f"{len(education)} education entr{'y' if len(education)==1 else 'ies'}, and "
        f"{len(resume_certs)} certification keyword(s) in the resume text. "
        f"Estimated total experience span: ~{total_years} year(s)."
    )

    if jd_must_skills:
        match_summary = (
            f"{len(matched_must)} of {len(jd_must_skills)} must-have skill keyword(s) found "
            f"({round(len(matched_must)/len(jd_must_skills)*100)}% coverage)"
        )
        if jd_nice_skills:
            match_summary += (
                f", plus {len(matched_nice)} of {len(jd_nice_skills)} nice-to-have skill keyword(s)."
            )
        else:
            match_summary += "."
    elif jd_skills:
        match_summary = (
            f"{len(matched_skills)} of {len(jd_skills)} job-description skill keyword(s) were found "
            f"in the resume ({skills_match}% skill keyword overlap)."
        )
    else:
        match_summary = (
            "No specific skill keywords from a known list were detected in the job description; "
            "scoring falls back to neutral defaults for the skills dimension."
        )

    strengths = [f"Resume includes the '{s}' keyword, matching a JD requirement." for s in matched_skills[:8]]
    if not strengths:
        strengths = ["No direct JD skill-keyword matches were found — see missing skills below."]

    weaknesses = [f"'{s}' is a must-have skill in the JD but wasn't found in the resume." for s in missing_must[:6]]
    weaknesses += [f"'{s}' is a nice-to-have skill in the JD but wasn't found in the resume." for s in missing_nice[:4]]
    if not jd_must_text.strip() == job_description.strip() and not missing_must and not missing_nice:
        pass  # no additional note needed
    if red_flags:
        weaknesses.extend(red_flags[:3])
    if not weaknesses:
        weaknesses = ["No notable gaps identified by the automated keyword scan."]

    interview_focus_areas = [
        f"Ask the candidate to describe hands-on experience with {s}, since it's a must-have for the "
        f"role but wasn't detected in the resume text." for s in missing_must[:6]
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
        f"overlap (must-have skills weighted higher than nice-to-have), an estimated experience "
        f"match of {experience_match}%, an education-keyword match of {education_match}%, and a "
        f"certification match of {certifications_match}%. This is a rule-based estimate, not an "
        f"AI judgment — use it as a first-pass filter."
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
