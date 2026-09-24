from backend.recommendations import build_course_links
from backend.scoring import clamp_score, weighted_final_score


def test_weighted_score():
    score = weighted_final_score(
        {
            "skill_match": 85,
            "experience_match": 60,
            "education_match": 100,
            "project_match": 80,
            "requirement_coverage": 75,
        }
    )
    assert score == 80


def test_clamp():
    assert clamp_score(-3) == 0
    assert clamp_score(140) == 100
    assert clamp_score("nope") == 0


def test_course_limit():
    links = build_course_links(["AWS", "Docker", "K8s", "SQL", "Rust"], limit=4)
    assert len(links) == 4
    assert "coursera.org/search" in links[0]["url"]
