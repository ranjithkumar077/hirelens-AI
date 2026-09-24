from urllib.parse import quote_plus


def build_course_links(missing_skills: list[str], limit: int = 4) -> list[dict]:
    links = []
    seen = set()
    for skill in missing_skills:
        key = skill.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        q = quote_plus(skill.strip())
        links.append(
            {
                "title": f"{skill.strip()} Fundamentals",
                "skill": skill.strip(),
                "platform": "Coursera",
                "url": f"https://www.coursera.org/search?query={q}",
            }
        )
        if len(links) >= limit:
            break
    return links
