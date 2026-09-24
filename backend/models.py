from typing import Literal

from pydantic import BaseModel, Field


class ComponentScores(BaseModel):
    skill_match: int = 0
    experience_match: int = 0
    education_match: int = 0
    project_match: int = 0
    requirement_coverage: int = 0


class EvidenceItem(BaseModel):
    claim: str = ""
    confidence: Literal["Strong Evidence", "Moderate Evidence", "Weak Evidence", "Not Found"] = "Not Found"
    reason: str = ""


class CourseRecommendation(BaseModel):
    title: str = ""
    skill: str = ""
    platform: str = "Coursera"
    url: str = ""


class AnalysisResult(BaseModel):
    job_title: str = ""
    resume_name: str = ""
    final_score: int = 0
    component_scores: ComponentScores = Field(default_factory=ComponentScores)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    partial_skills: list[str] = Field(default_factory=list)
    experience_alignment: str = ""
    education_alignment: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    suggestion: str = ""
    course_recommendations: list[CourseRecommendation] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    jd_text: str = ""
    resume_text: str = ""
    resume_name: str = "resume"
