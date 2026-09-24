import json
import re

from backend.config import GEMINI_API_KEY, MODEL_NAME
from backend.models import AnalysisResult, ComponentScores, CourseRecommendation, EvidenceItem
from backend.recommendations import build_course_links
from backend.scoring import clamp_score, weighted_final_score

SYSTEM_PROMPT = """You are a blunt, honest technical recruiter doing JD-resume ALIGNMENT analysis.
Do not flatter. Do not pad. Never accuse the candidate of lying.
You measure how strongly resume claims are supported by explicit evidence.

Score each component 0-100 independently. Do NOT invent the final score.
Components:
- skill_match: overlap of required JD skills vs resume skills/projects
- experience_match: years/seniority vs JD
- education_match: degree/field vs JD
- project_match: relevant projects vs JD responsibilities
- requirement_coverage: overall JD bullets covered

Evidence confidence must be one of:
Strong Evidence, Moderate Evidence, Weak Evidence, Not Found

Return ONLY valid JSON, no markdown fences, no preamble:
{
  "job_title": "",
  "component_scores": {
    "skill_match": 0,
    "experience_match": 0,
    "education_match": 0,
    "project_match": 0,
    "requirement_coverage": 0
  },
  "matched_skills": [],
  "missing_skills": [],
  "partial_skills": [],
  "experience_alignment": "",
  "education_alignment": "",
  "evidence": [
    {"claim": "", "confidence": "Strong Evidence", "reason": ""}
  ],
  "suggestion": "2-4 lines, honest, actionable, no fluff"
}

matched_skills max 6, missing_skills max 6, partial_skills max 4, evidence max 6.
suggestion must be 2-4 short lines.
"""


class AnalyzerError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise AnalyzerError("GEMINI_API_KEY is missing. Add it to your .env file.")

    try:
        from google import genai
    except ImportError:
        import google.generativeai as genai_legacy

        genai_legacy.configure(api_key=GEMINI_API_KEY)
        model = genai_legacy.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return (response.text or "").strip()

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return (response.text or "").strip()


def analyze_alignment(jd_text: str, resume_text: str, resume_name: str = "resume") -> AnalysisResult:
    if not (jd_text or "").strip():
        raise AnalyzerError("Job description is empty.")
    if not (resume_text or "").strip():
        raise AnalyzerError("Resume text is empty.")

    user_prompt = (
        f"{SYSTEM_PROMPT}\n\nJOB DESCRIPTION:\n{jd_text}\n\nRESUME ({resume_name}):\n{resume_text}"
    )

    last_error = None
    payload = None
    for attempt in range(2):
        prompt = user_prompt if attempt == 0 else user_prompt + "\n\nReturn valid JSON only."
        try:
            raw = _call_gemini(prompt)
            payload = _extract_json(raw)
            break
        except AnalyzerError:
            raise
        except Exception as exc:
            last_error = exc
            payload = None

    if payload is None:
        raise AnalyzerError(f"AI analysis failed: {last_error}")

    comps = payload.get("component_scores") or {}
    component_scores = ComponentScores(
        skill_match=clamp_score(comps.get("skill_match")),
        experience_match=clamp_score(comps.get("experience_match")),
        education_match=clamp_score(comps.get("education_match")),
        project_match=clamp_score(comps.get("project_match")),
        requirement_coverage=clamp_score(comps.get("requirement_coverage")),
    )
    final_score = weighted_final_score(component_scores.model_dump())

    evidence_items = []
    for item in (payload.get("evidence") or [])[:6]:
        conf = (item.get("confidence") or "Not Found").strip()
        if conf not in {"Strong Evidence", "Moderate Evidence", "Weak Evidence", "Not Found"}:
            conf = "Not Found"
        evidence_items.append(
            EvidenceItem(
                claim=str(item.get("claim") or "")[:120],
                confidence=conf,
                reason=str(item.get("reason") or "")[:200],
            )
        )

    missing = [str(s).strip() for s in (payload.get("missing_skills") or []) if str(s).strip()][:6]
    courses = [CourseRecommendation(**c) for c in build_course_links(missing, limit=4)]

    suggestion = str(payload.get("suggestion") or "").strip()
    if len(suggestion.splitlines()) > 6:
        suggestion = "\n".join(suggestion.splitlines()[:4])

    return AnalysisResult(
        job_title=str(payload.get("job_title") or "")[:80],
        resume_name=resume_name,
        final_score=final_score,
        component_scores=component_scores,
        matched_skills=[str(s).strip() for s in (payload.get("matched_skills") or []) if str(s).strip()][:6],
        missing_skills=missing,
        partial_skills=[str(s).strip() for s in (payload.get("partial_skills") or []) if str(s).strip()][:4],
        experience_alignment=str(payload.get("experience_alignment") or "")[:280],
        education_alignment=str(payload.get("education_alignment") or "")[:200],
        evidence=evidence_items,
        suggestion=suggestion,
        course_recommendations=courses,
    )
