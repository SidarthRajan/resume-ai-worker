# src/parser.py
from __future__ import annotations
import re, os
from typing import List, Dict
from .schema import Resume, Contact, ExperienceItem, EducationItem, ProjectItem

# Canonical headers (case-insensitive, tolerate spacing & trailing colon)
HEADER_ALIASES = {
    "CONTACT INFORMATION": ["CONTACT INFORMATION", "CONTACT", "INFO"],
    "SUMMARY": ["SUMMARY", "OBJECTIVE"],
    "EXPERIENCE": ["EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE"],
    "EDUCATION": ["EDUCATION"],
    "PROJECTS": ["PROJECTS"],
    "TECHNICAL SKILLS": ["TECHNICAL SKILLS", "SKILLS"],
    "CERTIFICATIONS & LICENSES": ["CERTIFICATIONS & LICENSES", "CERTIFICATIONS", "LICENSES"],
    "LANGUAGES": ["LANGUAGES", "LANGUAGE"],
    "VOLUNTEER EXPERIENCE": ["VOLUNTEER EXPERIENCE", "VOLUNTEER"],
}

HEADER_PATTERN = re.compile(
    r"^(?P<hdr>[A-Za-z][A-Za-z\s&]+?)(:?\s*)$"
)

def _read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        from docx import Document
        doc = Document(path)
        lines = [p.text for p in doc.paragraphs]
        return "\n".join(lines)
    elif ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext == ".txt":
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError("Unsupported file type. Use .docx, .pdf, or .txt")

def _normalize_text(text: str) -> str:
    # Convert tabs to spaces, collapse multiple spaces, trim ends
    t = text.replace("\t", "    ")
    t = re.sub(r"\u00A0", " ", t)  # non-breaking space
    t = re.sub(r"[ \t]+", " ", t)
    # Keep line breaks; trim each line
    t = "\n".join(l.strip() for l in t.splitlines())
    # Remove runs of empty lines > 2
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _canonical_header(s: str) -> str | None:
    s_clean = re.sub(r":\s*$", "", s.upper().strip())
    for canon, aliases in HEADER_ALIASES.items():
        if s_clean == canon or s_clean in aliases:
            return canon
    return None

def _split_sections(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    sections: Dict[str, str] = {}
    indices: List[int] = []
    names: List[str] = []

    for i, line in enumerate(lines):
        m = HEADER_PATTERN.match(line.strip())
        if not m:
            continue
        hdr = _canonical_header(m.group("hdr"))
        if hdr:
            indices.append(i)
            names.append(hdr)

    for j, start in enumerate(indices):
        end = indices[j + 1] if j + 1 < len(indices) else len(lines)
        body = "\n".join(lines[start + 1:end]).strip()
        if body:
            sections[names[j]] = body
    return sections

def _parse_contact_block(full_text: str) -> Contact:
    # Contact is everything before the first detected header
    m = HEADER_PATTERN.search(full_text)
    top = full_text[:m.start()] if m else full_text
    lines = top.splitlines()
    name = lines[0].strip() if lines else None

    # Join all contact lines and search for patterns
    contact_text = "\n".join(lines)
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contact_text)
    phone = re.search(r"(?:\+1\s*)?\(?\d{3}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{4}", contact_text)
    
    # Look for location pattern, but exclude the name line
    loc = None
    for line in lines[1:]:  # Skip the first line (name)
        loc_match = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", line)
        if loc_match:
            loc = loc_match.group(0)
            break
    
    website = re.search(r"(https?://\S+|www\.\S+|\S+\.com\b)", contact_text)
    linkedin = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", contact_text, re.I)
    github = re.search(r"(?:https?://)?(?:www\.)?github\.com/\S+", contact_text, re.I)

    return Contact(
        name=name or None,
        email=email.group(0) if email else None,
        phone=phone.group(0) if phone else None,
        location=loc,
        website=website.group(0) if website else None,
        linkedin=linkedin.group(0) if linkedin else None,
        github=github.group(0) if github else None,
    )

def _split_blocks_by_blanklines(block: str) -> List[str]:
    return [c.strip() for c in re.split(r"\n\s*\n", block) if c.strip()]

def _bullets(text: str) -> List[str]:
    # Accept both true bullets and plain lines as bullets
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: List[str] = []
    for l in lines:
        l2 = re.sub(r"^\s*(?:[-•*]|\d+\.)\s+", "", l)
        out.append(l2)
    return out

def _parse_experience(block: str) -> List[ExperienceItem]:
    """
    Handles patterns like:
      Company
      City, ST
      Title
      Month YYYY - Present
      bullet...
    """
    items: List[ExperienceItem] = []
    chunks = _split_blocks_by_blanklines(block)
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue

        # Find company and location
        company = None
        location = None
        title = None
        start_date = None
        end_date = None
        
        # Look for location pattern in first few lines
        for i, line in enumerate(lines[:3]):
            loc_match = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", line)
            if loc_match:
                location = loc_match.group(0)
                # If this line also contains company name, extract it
                potential_company = line.replace(location, "").strip(" -–—\u2022").strip()
                if potential_company and not company:
                    company = potential_company
                break
        
        # If no company found yet, first line is likely company
        if not company and lines:
            company = lines[0].strip()
        
        # Look for title and dates in subsequent lines
        for i, line in enumerate(lines[1:4]):
            # Check if line contains date range
            dr = re.search(r"(?i)((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\s*[-–—]\s*(Present|\d{4}(?:|\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*))", line)
            if dr:
                start_date = dr.group(1).strip()
                end_date = "Present" if "Present" in dr.group(0) else dr.group(3).strip()
                # Title is the part before the date range
                potential_title = line.replace(dr.group(0), "").strip(" -–—\u2022").strip()
                if potential_title and not title:
                    title = potential_title
                break
            elif not title and line and not re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", line):
                # If no date found and line doesn't look like location, it might be title
                title = line.strip()
        
        # Get bullets from remaining lines
        bullet_start = 0
        for i, line in enumerate(lines):
            if title and title in line:
                bullet_start = i + 1
                break
            elif start_date and start_date in line:
                bullet_start = i + 1
                break
        
        desc = "\n".join(lines[bullet_start:]) if bullet_start < len(lines) else ""
        items.append(ExperienceItem(
            title=title or None,
            company=company or None,
            location=location,
            start_date=start_date,
            end_date=end_date,
            bullets=_bullets(desc),
        ))
    return items

def _parse_education(block: str) -> List[EducationItem]:
    items: List[EducationItem] = []
    chunks = _split_blocks_by_blanklines(block)
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue
        
        # Find school and location
        school = None
        location = None
        degree = None
        gpa = None
        dates = None
        
        # Look for location pattern
        for i, line in enumerate(lines[:3]):
            loc_match = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2,}\b", line)
            if loc_match:
                location = loc_match.group(0)
                # If this line also contains school name, extract it
                potential_school = line.replace(location, "").strip(" -–—\u2022").strip()
                if potential_school and not school:
                    school = potential_school
                break
        
        # If no school found yet, first line is likely school
        if not school and lines:
            school = lines[0].strip()
        
        # Look for degree, GPA, and dates in subsequent lines
        for i, line in enumerate(lines[1:4]):
            # Check for GPA
            gpa_match = re.search(r"\bGPA[:\s]+([\d\.]+\/?[\d\.]*)", line, re.I)
            if gpa_match and not gpa:
                gpa = gpa_match.group(1)
            
            # Check for dates
            date_match = re.search(r"(?i)(?:Expected\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}|\b(?:\w+\s)?\d{4}\b", line)
            if date_match and not dates:
                dates = date_match.group(0)
            
            # If line doesn't look like location and contains degree-like text
            if not re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2,}\b", line) and not degree:
                degree = line.strip()

        # Get bullets from remaining lines
        bullet_start = 0
        for i, line in enumerate(lines):
            if degree and degree in line:
                bullet_start = i + 1
                break
            elif dates and dates in line:
                bullet_start = i + 1
                break
        
        bullets = _bullets("\n".join(lines[bullet_start:])) if bullet_start < len(lines) else []
        items.append(EducationItem(
            school=school or None,
            location=location,
            degree=degree or None,
            major=None,
            gpa=gpa,
            dates=dates,
            bullets=bullets
        ))
    return items

def _parse_projects(block: str) -> List[ProjectItem]:
    items: List[ProjectItem] = []
    chunks = _split_blocks_by_blanklines(block)
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines: continue
        header = lines[0]
        loc = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", c)
        dates = re.search(r"(?:\b20\d{2}\b|\b19\d{2}\b).*?(?:Present|\b20\d{2}\b|\b19\d{2}\b)?", c)
        items.append(ProjectItem(
            name=header.strip(),
            location=(loc.group(0) if loc else None),
            dates=(dates.group(0) if dates else None),
            bullets=_bullets("\n".join(lines[1:])) if len(lines) > 1 else [],
            skills=[]
        ))
    return items

def _parse_skills(block: str) -> List[str]:
    """
    Handles category lines like:
    'Programming Languages & Frameworks: Python, TypeScript, ...'
    Flattens everything into one deduped list.
    """
    skills: List[str] = []
    for line in block.splitlines():
        if not line.strip(): continue
        # take RHS after colon if present
        rhs = line.split(":", 1)[1] if ":" in line else line
        
        # Handle parentheses by splitting on commas and cleaning up
        # First split on commas outside parentheses
        parts = []
        current_part = ""
        paren_count = 0
        
        for char in rhs:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == ',' and paren_count == 0:
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
                continue
            current_part += char
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        # Clean up each part
        for part in parts:
            part = part.strip()
            if part:
                # Remove trailing parentheses if they're empty or just contain whitespace
                part = re.sub(r'\(\s*\)$', '', part)
                if part.strip():
                    skills.append(part.strip())
    
    # dedupe preserve order
    seen = set(); out = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k); out.append(s)
    return out

def _parse_certs(block: str) -> List[str]:
    """
    Name (Year)
    Organization
    (blank)
    """
    out: List[str] = []
    lines = [l for l in block.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip if this looks like a language entry
        if re.search(r'\(Native\)|\(Conversational\)|\(Basic\)', line):
            i += 1
            continue
            
        # Check if line contains certification pattern
        if re.search(r'Certified|Certification|AWS|Google|Microsoft|CSM|PMP', line, re.I):
            name = line
            org = None
            # Peek next if not header-y and not a language
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if (not HEADER_PATTERN.match(next_line) and 
                    not re.search(r'\(Native\)|\(Conversational\)|\(Basic\)', next_line) and
                    not re.search(r'Languages?', next_line, re.I)):
                    org = next_line
                    i += 1
            combo = name if not org else f"{name} — {org}"
            out.append(combo)
        i += 1
    return out

def _parse_languages(block: str) -> List[str]:
    out: List[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line: continue
        
        # Skip if this doesn't look like a language entry
        if not re.search(r'\(Native\)|\(Conversational\)|\(Basic\)|\(Fluent\)|\(Intermediate\)', line):
            continue
            
        # Normalize '(Conversational)' etc.
        m = re.match(r"([A-Za-z\s]+)\s*\(([^)]+)\)", line)
        if m:
            lang = m.group(1).strip()
            level = m.group(2).strip().title()
            out.append(f"{lang} — {level}")
        else:
            # Handle cases where languages might be on the same line
            parts = re.split(r'\s+—\s+', line)
            for part in parts:
                if re.search(r'\(Native\)|\(Conversational\)|\(Basic\)|\(Fluent\)|\(Intermediate\)', part):
                    m = re.match(r"([A-Za-z\s]+)\s*\(([^)]+)\)", part)
                    if m:
                        lang = m.group(1).strip()
                        level = m.group(2).strip().title()
                        out.append(f"{lang} — {level}")
    return out

def parse_resume(path: str) -> dict:
    raw = _read_text(path)
    text = _normalize_text(raw)
    sections = _split_sections(text)
    r = Resume()

    # Contact
    r.contact = _parse_contact_block(text)

    # Summary / Objective
    if "SUMMARY" in sections:
        r.summary = sections["SUMMARY"]
    elif "OBJECTIVE" in sections:
        r.summary = sections["OBJECTIVE"]

    # Experience
    for key in ["EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE"]:
        if key in sections:
            r.experience = _parse_experience(sections[key]); break

    # Education
    if "EDUCATION" in sections:
        r.education = _parse_education(sections["EDUCATION"])

    # Projects
    if "PROJECTS" in sections:
        r.projects = _parse_projects(sections["PROJECTS"])

    # Technical Skills / Skills
    for key in ["TECHNICAL SKILLS", "SKILLS"]:
        if key in sections:
            r.skills = _parse_skills(sections[key]); break

    # Certifications
    for key in ["CERTIFICATIONS & LICENSES", "CERTIFICATIONS", "LICENSES"]:
        if key in sections:
            r.certifications = _parse_certs(sections[key]); break

    # Languages
    for key in ["LANGUAGES", "LANGUAGE"]:
        if key in sections:
            r.languages = _parse_languages(sections[key]); break

    # Volunteer
    for key in ["VOLUNTEER EXPERIENCE", "VOLUNTEER"]:
        if key in sections:
            r.volunteer = _parse_projects(sections[key]); break

    return r.model_dump()
