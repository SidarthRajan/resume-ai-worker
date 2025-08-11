# src/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Contact(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

class ExperienceItem(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)

class EducationItem(BaseModel):
    school: Optional[str] = None
    location: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    gpa: Optional[str] = None
    dates: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)

class ProjectItem(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    dates: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)

class Resume(BaseModel):
    contact: Contact = Contact()
    summary: Optional[str] = None
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    volunteer: List[ProjectItem] = Field(default_factory=list)

    # Allow round‑tripping arbitrary extras if needed later
    meta: Dict[str, str] = Field(default_factory=dict)
