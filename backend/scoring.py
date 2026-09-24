WEIGHTS = {
    "skill_match": 0.40,
    "experience_match": 0.25,
    "education_match": 0.15,
    "project_match": 0.10,
    "requirement_coverage": 0.10,
}


def clamp_score(value) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = 0
    return max(0, min(100, n))


def weighted_final_score(components: dict) -> int:
    total = 0.0
    for key, weight in WEIGHTS.items():
        total += clamp_score(components.get(key, 0)) * weight
    return clamp_score(total)


def why_this_score(components: dict, final_score: int, missing_skills: list[str]) -> str:
    lines = [
        "📊 <b>WHY THIS SCORE?</b>",
        "",
        f"Skills          {clamp_score(components.get('skill_match'))}/100",
        f"Experience      {clamp_score(components.get('experience_match'))}/100",
        f"Education       {clamp_score(components.get('education_match'))}/100",
        f"Projects        {clamp_score(components.get('project_match'))}/100",
        f"Requirements    {clamp_score(components.get('requirement_coverage'))}/100",
        "",
        f"Weighted score: {final_score}%",
        "(40% skills + 25% experience + 15% education + 10% projects + 10% requirements)",
    ]
    if missing_skills:
        lines.append("")
        lines.append("Main gap: " + ", ".join(missing_skills[:5]))
    return "\n".join(lines)
