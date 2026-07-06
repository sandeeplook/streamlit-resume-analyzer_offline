# AI Resume Verification & JD Match Analyzer — Offline Edition

A single-process Streamlit app that reviews a resume against a job
description **entirely offline** — no external API, no AI model, no account,
no billing. All analysis is done with local text parsing, keyword matching,
and rule-based scoring in plain Python.

- **No database.** Everything runs in memory for the current session.
- **No authentication.**
- **No API key required.** Nothing leaves the app — fully self-contained.

## What it can and can't do

Because there's no AI model involved, this is a **keyword/pattern-matching**
tool, not a reasoning engine. Be aware of the trade-off:

**It can:**
- Detect resume section headers (Skills / Experience / Education /
  Certifications) and scope extraction to the right section
- Match skills via exact keywords, common synonyms/abbreviations ("ML" →
  Machine Learning, "K8s" → Kubernetes, "JS" → JavaScript, etc. — see
  `services/skills_data.py`), and fuzzy matching for typos/spacing variants
  found in a resume's Skills section (e.g. "Djnago" → Django)
- Estimate years of experience from date ranges (including month-name
  formats like "Jun 2017 - Dec 2019")
- Pull out experience entries (title/company/duration/bullets), education,
  and certifications via pattern matching
- Split a job description into "must-have" vs "nice-to-have" requirements
  (when the JD has those headers) and weight missing must-have skills more
  heavily than missing nice-to-have ones in the score
- Flag basic red flags: overlapping employment dates, missing contact info,
  unusually short resume text
- Extract PDF text via `pdfplumber` (falls back to `pypdf` if needed), which
  preserves line breaks/layout better than `pypdf` alone — important since
  the parsing above depends on line structure

**It can't:**
- Understand context or judge whether experience is genuinely relevant
- Write a natural-language, reasoned recommendation — summaries here are
  templated sentences built from the extracted data, not AI-generated prose
- Reliably catch subtle inconsistencies or exaggerations
- Handle every resume layout — heavily designed/columnar resumes, scanned
  images, or unusual section naming will still degrade results
- Match a skill that isn't in `services/skills_data.py` and has no close
  fuzzy variant of something that is — the skill/synonym list is curated,
  not exhaustive

Treat its output as a **first-pass filter**, not a final verdict.

## Project structure

```
streamlit-resume-analyzer/
├── app.py                          # Streamlit UI + orchestration (entry point)
├── config.py                       # Settings (upload limits, etc.) — no API keys needed
├── services/
│   ├── text_extraction.py          # PDF/DOCX -> plain text
│   ├── rule_based_analyzer.py      # Core offline analysis engine (regex + keyword rules)
│   ├── skills_data.py              # Curated skills / certifications / degree keyword lists
│   ├── report_export.py            # Markdown + PDF report generation
│   └── exceptions.py               # Typed app errors
├── requirements.txt
├── runtime.txt                     # Pins Python version for Streamlit Cloud
├── .streamlit/
│   ├── config.toml                 # Theme
│   └── secrets.toml.example        # Optional — only used for MAX_UPLOAD_SIZE_MB override
└── .gitignore
```

## Run locally

```bash
cd streamlit-resume-analyzer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. No secrets file is required to run it.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo, with `app.py` and `requirements.txt`
   at the repo root (or note the subfolder path).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**.
3. Select your repo/branch, set **Main file path** to `app.py`.
4. Click **Deploy** — no secrets need to be configured for this offline
   edition. (`.streamlit/secrets.toml.example` is optional and only relevant
   if you want to override `MAX_UPLOAD_SIZE_MB`.)

If you hit a Python-version build error (e.g. Pillow failing to compile),
set the Python version explicitly in the app's **Settings → General →
Python version** to `3.11`, matching the included `runtime.txt`.

## How the 3 stages map onto one script

- **Upload & JD input** — file uploader + tabbed paste/upload JD box
- **Analysis progress** — `st.status(...)` panel with live step updates
  while the local analyzer runs (this completes almost instantly, since
  there's no network round-trip)
- **Results dashboard** — score badge, per-dimension metrics, `st.expander`
  for every analysis section, and **Download PDF / Download Markdown**
  buttons generated server-side in Python

## Extending it

- Add more terms to `services/skills_data.py` (`SKILLS`,
  `SKILL_SYNONYMS`, `CERTIFICATION_KEYWORDS`, `DEGREE_KEYWORDS`,
  `SECTION_HEADERS`) to widen what gets detected.
- Scoring weights and thresholds live in `services/rule_based_analyzer.py`
  (`analyze_resume()`), if you want to tune how skills/experience/education/
  certifications combine into the overall score, or how much must-have vs
  nice-to-have skills matter.
- The fuzzy-match cutoff (`cutoff=0.84` in `_fuzzy_match_tokens_to_skills`)
  controls how lenient typo-matching is — lower it to catch more variants
  at the risk of more false positives.
