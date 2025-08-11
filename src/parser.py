# src/parser.py
from __future__ import annotations
import re, json, os
from typing import List, Dict
from pydantic import ValidationError
from .schema import Resume, Contact, ExperienceItem, EducationItem, ProjectItem

SECTION_HEADERS = [
    "Contact Information", "Summary", "Objective", "Experience", "Work Experience",
    "Professional Experience", "Education", "Projects", "Skills", "Technical Skills",
    "Certifications", "Licenses", "Certifications & Licenses", "Languages",
    "Volunteer", "Volunteer Experience"
]

def _read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext == ".txt":
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError("Unsupported file type. Use .docx, .pdf, or .txt")

def _split_sections(text: str) -> Dict[str, str]:
    lines = [l.rstrip() for l in text.splitlines()]
    # Identify header lines (strict match ignoring trailing ':' / whitespace)
    header_idxs: List[int] = []
    for i, line in enumerate(lines):
        stripped = re.sub(r":\s*$", "", line, flags=re.IGNORECASE).strip()
        if any(stripped.lower() == h.lower() for h in SECTION_HEADERS):
            header_idxs.append(i)

    sections: Dict[str, str] = {}
    for idx, start in enumerate(header_idxs):
        end = header_idxs[idx + 1] if idx + 1 < len(header_idxs) else len(lines)
        header = re.sub(r":\s*$", "", lines[start]).strip()
        body = "\n".join(l for l in lines[start + 1:end]).strip()
        if body:
            sections[header] = body
    return sections

def _parse_contact_block(text: str) -> Contact:
    # Heuristic: everything before first known header is contact block
    first_header_match = re.search(
        r"(?mi)^(?:%s)\s*:?\s*$" % "|".join(re.escape(h) for h in SECTION_HEADERS),
        text
    )
    top = text[: first_header_match.start()] if first_header_match else text

    name = top.splitlines()[0].strip() if top.splitlines() else None
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", top)
    phone = re.search(r"(?:\+1\s*)?\(?\d{3}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{4}", top)
    # Simple city, ST pattern
    loc = re.search(r"([A-Za-z][A-Za-z\.\s]+),\s*([A-Za-z]{2})\b", top)
    website = re.search(r"(https?://\S+|www\.\S+|\S+\.com\b)", top)
    linkedin = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", top, re.I)
    github = re.search(r"(?:https?://)?(?:www\.)?github\.com/\S+", top, re.I)

    return Contact(
        name=name or None,
        email=email.group(0) if email else None,
        phone=phone.group(0) if phone else None,
        location=(loc.group(0) if loc else None),
        website=website.group(0) if website else None,
        linkedin=linkedin.group(0) if linkedin else None,
        github=github.group(0) if github else None,
    )

def _bullets(block: str) -> List[str]:
    # split on bullet markers or newlines with leading dash/•/*
    parts = re.split(r"(?m)^\s*(?:[-•*]|\d+\.)\s+|\n", block)
    bullets = [p.strip() for p in parts if p and len(p.strip()) > 1]
    return bullets

def _parse_experience(block: str) -> List[ExperienceItem]:
    items: List[ExperienceItem] = []
    # naive split by blank lines between roles
    chunks = [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]
    for c in chunks:
        lines = c.splitlines()
        header = lines[0] if lines else ""
        # Try patterns: "Title — Company, City ST   Jan 2022 – Present"
        date = re.search(r"(?i)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}.*?(Present|\d{4})", header)
        title_company = re.split(r"\s+—\s+| - ", header, maxsplit=1)
        title = title_company[0].strip() if title_company else None
        company = title_company[1].strip() if len(title_company) > 1 else None
        loc_match = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", header)
        bullets = _bullets("\n".join(lines[1:])) if len(lines) > 1 else []
        items.append(ExperienceItem(
            title=title or None,
            company=company or None,
            location=(loc_match.group(0) if loc_match else None),
            start_date=(date.group(0).split("–")[0].strip() if date else None),
            end_date=("Present" if date and "Present" in date.group(0) else None),
            bullets=bullets
        ))
    return items

def _parse_education(block: str) -> List[EducationItem]:
    items: List[EducationItem] = []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]
    for c in chunks:
        lines = c.splitlines()
        header = lines[0] if lines else ""
        school = header.strip()
        degree_line = lines[1] if len(lines) > 1 else ""
        gpa = re.search(r"\bGPA[:\s]+([\d\.]+\/?[\d\.]*)", c, re.I)
        dates = re.search(r"(?i)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}.*?\d{4}|Expected\s+\w+\s+\d{4}", c)
        loc = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", c)
        bullets = _bullets("\n".join(lines[2:])) if len(lines) > 2 else []
        items.append(EducationItem(
            school=school or None,
            degree=degree_line or None,
            gpa=(gpa.group(1) if gpa else None),
            dates=(dates.group(0) if dates else None),
            location=(loc.group(0) if loc else None),
            bullets=bullets
        ))
    return items

def _parse_projects(block: str) -> List[ProjectItem]:
    items: List[ProjectItem] = []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]
    for c in chunks:
        lines = c.splitlines()
        header = lines[0] if lines else ""
        loc = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", header)
        dates = re.search(r"(?:\b20\d{2}\b|\b19\d{2}\b).*?(?:Present|\b20\d{2}\b|\b19\d{2}\b)?", c)
        items.append(ProjectItem(
            name=header or None,
            location=(loc.group(0) if loc else None),
            dates=(dates.group(0) if dates else None),
            bullets=_bullets("\n".join(lines[1:])) if len(lines) > 1 else []
        ))
    return items

def parse_resume(path: str) -> dict:
    text = _read_text(path)
    sections = _split_sections(text)
    resume = Resume()  # defaults
    # Contact from top block
    resume.contact = _parse_contact_block(text)
    # Summary/Objective
    for key in ["Summary", "Objective"]:
        if key in sections and not resume.summary:
            resume.summary = sections[key].strip()
    # Experience
    for key in ["Experience", "Work Experience", "Professional Experience"]:
        if key in sections:
            resume.experience = _parse_experience(sections[key]); break
    # Education
    if "Education" in sections:
        resume.education = _parse_education(sections["Education"])
    # Projects
    if "Projects" in sections:
        resume.projects = _parse_projects(sections["Projects"])
    # Skills (comma/pipe/newline split)
    for key in ["Technical Skills", "Skills"]:
        if key in sections and not resume.skills:
            raw = sections[key]
            parts = re.split(r"[,\|\n]", raw)
            resume.skills = [p.strip() for p in parts if p.strip()]
    # Certifications
    for key in ["Certifications & Licenses", "Certifications", "Licenses"]:
        if key in sections and not resume.certifications:
            resume.certifications = [s.strip("-•* ").strip() for s in sections[key].splitlines() if s.strip()]
    # Languages
    if "Languages" in sections:
        resume.languages = [s.strip("-•* ").strip() for s in sections["Languages"].splitlines() if s.strip()]
    # Volunteer
    for key in ["Volunteer Experience", "Volunteer"]:
        if key in sections and not resume.volunteer:
            resume.volunteer = _parse_projects(sections[key])  # reuse simple parser
    # Validate & return dict
    try:
        return Resume.model_validate(resume).model_dump()
    except ValidationError as e:
        # Hard fail shouldn't happen; return best-effort dict for visibility
        return resume.model_dump()
