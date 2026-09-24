from backend.analyzer import analyze_alignment

jd = (
    "We are hiring a Python ML Engineer with AWS, Docker, Kubernetes, "
    "and 2+ years professional experience. SQL and Git required."
)
resume = (
    "Intern. Built a Python ML classifier for iris data as a college project. "
    "Skills: Python, SQL, Git. No AWS or Docker production work. No full-time job."
)
result = analyze_alignment(jd, resume, "weak.pdf")
print(result.final_score)
print(result.matched_skills)
print(result.missing_skills)
print(result.suggestion[:120])
