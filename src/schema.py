# src/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any

Priority = Literal["high", "med", "low"]

class Contact(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    # extras for complex resumes
    citizenship: Optional[str] = None
    clearance: Optional[str] = None

class ExperienceItem(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    priority: Optional[Priority] = None  # let tailoring mark importance

class EducationItem(BaseModel):
    school: Optional[str] = None
    location: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    gpa: Optional[str] = None
    dates: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    concentrations: List[str] = Field(default_factory=list)  # e.g., AI, Robotics
    coursework: List[str] = Field(default_factory=list)
    honors: List[str] = Field(default_factory=list)
    priority: Optional[Priority] = None

class ProjectItem(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    dates: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    priority: Optional[Priority] = None

class CertificationItem(BaseModel):
    name: Optional[str] = None       # "AWS Solutions Architect - Associate"
    organization: Optional[str] = None  # "AWS"
    year: Optional[str] = None
    priority: Optional[Priority] = None

class Resume(BaseModel):
    contact: Contact = Contact()
    summary: Optional[str] = None

    # core sections
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)

    # skills (both flat and categorized)
    skills: List[str] = Field(default_factory=list)
    skills_matrix: Dict[str, List[str]] = Field(default_factory=dict)
    # e.g. {
    #   "Programming Languages & Frameworks": [...],
    #   "Backend & Infrastructure": [...],
    #   "Cloud & DevOps": [...],
    #   "AI, LLM, & Evaluation": [...],
    #   "Test, Monitoring, & Tooling": [...]
    # }

    certifications: List[CertificationItem] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    volunteer: List[ProjectItem] = Field(default_factory=list)

    # optional extras some templates list
    honors: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    affiliations: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)

    # meta & layout
    meta: Dict[str, Any] = Field(default_factory=dict)
    # meta may include:
    #   one_page: bool
    #   section_order: List[str]
    #   caps: { "experience_bullets": 6, "projects": 2, ... }
