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
    t = text.replace("\t", " ")
    t = re.sub(r"\u00A0", " ", t)  # non-breaking space
    t = re.sub(r"[ \t]+", " ", t)  # Keep line breaks; trim each line
    t = "\n".join(l.strip() for l in t.splitlines())
    # Remove runs of empty lines > 2
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _normalize_text_preserve_tabs(text: str) -> str:
    """Normalize text but preserve tab separators for parsing"""
    t = text
    t = re.sub(r"\u00A0", " ", t)  # non-breaking space
    t = re.sub(r"[ ]+", " ", t)  # Collapse multiple spaces but preserve tabs
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

def _extract_dates_from_text(text: str) -> tuple[str | None, str | None]:
    """Extract start and end dates from text, handling various formats"""
    # Pattern for date ranges like "May – August 2022", "July 2023 - Present", etc.
    date_pattern = re.compile(
        r"(?i)((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-–—]\s*(Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})"
    )
    match = date_pattern.search(text)
    if match:
        start_date = match.group(1).strip()
        end_date = "Present" if match.group(2) == "Present" else match.group(2).strip()
        return start_date, end_date
    
    # Pattern for single dates like "May 2023"
    single_date = re.search(r"(?i)((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", text)
    if single_date:
        return single_date.group(1).strip(), None
    
    return None, None

def _extract_location_from_text(text: str) -> str | None:
    """Extract location pattern from text"""
    loc_pattern = re.search(r"[A-Za-z][A-Za-z\.\s]+,\s*[A-Za-z]{2}\b", text)
    return loc_pattern.group(0) if loc_pattern else None

def _parse_experience(block: str) -> List[ExperienceItem]:
    """Generalized experience parsing for both simple and complex formats"""
    items: List[ExperienceItem] = []
    chunks = _split_blocks_by_blanklines(block)
    
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue
        
        # First line: could be simple format (title — company, location dates) 
        # or complex format (company location)
        first_line = lines[0]
        
        # Check if this is simple format (contains "—")
        if "—" in first_line:
            # Simple format: "Title — Company, Location   Dates"
            parts = re.split(r'\s+—\s+', first_line.strip())
            if len(parts) >= 2:
                title = parts[0].strip()
                company_location_dates = parts[1].strip()
                
                # Extract location and dates from the second part
                location = _extract_location_from_text(company_location_dates)
                company = company_location_dates
                if location:
                    company = company_location_dates.replace(location, "").strip(" ,")
                
                # Extract dates
                start_date, end_date = _extract_dates_from_text(company_location_dates)
                
                # Bullets start from second line
                desc = "\n".join(lines[1:]) if len(lines) > 1 else ""
                
                items.append(ExperienceItem(
                    title=title or None,
                    company=company or None,
                    location=location,
                    start_date=start_date,
                    end_date=end_date,
                    bullets=_bullets(desc),
                ))
                continue
        
        # Complex format: company and location on first line, title and dates on second
        company_line = lines[0]
        
        # Split by multiple spaces or tabs to separate company from location
        parts = re.split(r'\s{2,}|\t', company_line.strip())
        if len(parts) >= 2:
            company = parts[0].strip()
            location = parts[1].strip()
        else:
            # Fallback: try to extract location pattern
            location = _extract_location_from_text(company_line)
            company = company_line
            if location:
                company = company_line.replace(location, "").strip(" -–—\u2022").strip()
        
        # Second line: title and dates (separated by tabs)
        title = None
        start_date = None
        end_date = None
        
        if len(lines) >= 2:
            title_line = lines[1]
            
            # Split by multiple spaces or tabs to separate title from dates
            title_parts = re.split(r'\s{2,}|\t', title_line.strip())
            if len(title_parts) >= 2:
                title = title_parts[0].strip()
                date_text = title_parts[1].strip()
                start_date, end_date = _extract_dates_from_text(date_text)
            else:
                # Fallback: extract dates from the whole line
                start_date, end_date = _extract_dates_from_text(title_line)
                if start_date:
                    # Remove dates from title
                    title = re.sub(r"(?i)((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-–—]\s*(Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", "", title_line).strip(" -–—\u2022").strip()
                else:
                    title = title_line.strip()
        
        # Remaining lines are bullets
        desc = "\n".join(lines[2:]) if len(lines) > 2 else ""
        
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
    """Generalized education parsing for both simple and complex formats"""
    items: List[EducationItem] = []
    chunks = _split_blocks_by_blanklines(block)
    
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue
        
        # First line: school name (and possibly location)
        school_line = lines[0]
        
        # Check if this line contains location pattern
        location = _extract_location_from_text(school_line)
        school = school_line
        if location:
            # Complex format: school and location on same line
            school = school_line.replace(location, "").strip(" -–—\u2022").strip()
        else:
            # Simple format: just school name
            school = school_line.strip()
        
        # Second line: degree information
        degree = None
        gpa = None
        dates = None
        
        if len(lines) >= 2:
            degree_line = lines[1]
            # Extract GPA
            gpa_match = re.search(r"\bGPA[:\s]+([\d\.]+\/?[\d\.]*)", degree_line, re.I)
            if gpa_match:
                gpa = gpa_match.group(1)
            
            # Extract dates
            start_date, end_date = _extract_dates_from_text(degree_line)
            if start_date:
                dates = f"{start_date} - {end_date}" if end_date else start_date
            
            # Degree is the cleaned line
            degree = degree_line
        
        # Remaining lines are bullets
        bullets = _bullets("\n".join(lines[2:])) if len(lines) > 2 else []
        
        # For simple format, dates might be in bullets
        if not dates and bullets:
            for bullet in bullets:
                start_date, end_date = _extract_dates_from_text(bullet)
                if start_date:
                    dates = f"{start_date} - {end_date}" if end_date else start_date
                    # Remove the date bullet
                    bullets = [b for b in bullets if b != bullet]
                    break
        
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
    """Generalized project parsing for both simple and complex formats"""
    items: List[ProjectItem] = []
    chunks = _split_blocks_by_blanklines(block)
    
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue
        
        # First line: project name and possibly location
        name_line = lines[0]
        
        # Check if this is simple format (contains "—")
        if "—" in name_line:
            # Simple format: "Project Name — Year"
            parts = re.split(r'\s+—\s+', name_line.strip())
            if len(parts) >= 2:
                name = parts[0].strip()
                date_text = parts[1].strip()
                
                # Extract dates
                start_date, end_date = _extract_dates_from_text(date_text)
                dates = f"{start_date} - {end_date}" if start_date and end_date else start_date
                
                # All remaining lines are bullets
                bullets = _bullets("\n".join(lines[1:])) if len(lines) > 1 else []
                
                items.append(ProjectItem(
                    name=name or None,
                    location=None,
                    dates=dates,
                    bullets=bullets,
                    skills=[]
                ))
                continue
        
        # Complex format: name and location on first line, tech stack and dates on second
        # Split by multiple spaces or tabs to separate name from location
        parts = re.split(r'\s{2,}|\t', name_line.strip())
        if len(parts) >= 2:
            name = parts[0].strip()
            location = parts[1].strip()
        else:
            # Fallback: try to extract location pattern
            location = _extract_location_from_text(name_line)
            name = name_line
            if location:
                name = name_line.replace(location, "").strip(" -–—\u2022").strip()
        
        # Second line: tech stack and dates (separated by tabs)
        skills = []
        dates = None
        
        if len(lines) >= 2:
            tech_line = lines[1]
            
            # Split by multiple spaces or tabs to separate tech stack from dates
            tech_parts = re.split(r'\s{2,}|\t', tech_line.strip())
            if len(tech_parts) >= 2:
                tech_stack = tech_parts[0].strip()
                date_text = tech_parts[1].strip()
                
                # Extract skills from tech stack (pipe-separated)
                if tech_stack:
                    skills = [s.strip() for s in tech_stack.split('|') if s.strip()]
                
                # Extract dates
                start_date, end_date = _extract_dates_from_text(date_text)
                if start_date:
                    dates = f"{start_date} - {end_date}" if end_date else start_date
            else:
                # Fallback: extract dates from the whole line
                start_date, end_date = _extract_dates_from_text(tech_line)
                if start_date:
                    dates = f"{start_date} - {end_date}" if end_date else start_date
                
                # Try to extract tech stack from the line
                tech_stack = re.sub(r"(?i)((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-–—]\s*(Present|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", "", tech_line).strip()
                if tech_stack:
                    skills = [s.strip() for s in tech_stack.split('|') if s.strip()]
        
        # Remaining lines are bullets
        bullets = _bullets("\n".join(lines[2:])) if len(lines) > 2 else []
        
        items.append(ProjectItem(
            name=name or None,
            location=location,
            dates=dates,
            bullets=bullets,
            skills=skills
        ))
    
    return items

def _parse_volunteer(block: str) -> List[ProjectItem]:
    """Parse volunteer sections with organization name and dates on second line"""
    items: List[ProjectItem] = []
    chunks = _split_blocks_by_blanklines(block)
    
    for c in chunks:
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines:
            continue
        
        # First line: volunteer role and location (separated by tabs)
        name_line = lines[0]
        
        # Split by multiple spaces or tabs to separate name from location
        parts = re.split(r'\s{2,}|\t', name_line.strip())
        if len(parts) >= 2:
            name = parts[0].strip()
            location = parts[1].strip()
        else:
            # Fallback: try to extract location pattern
            location = _extract_location_from_text(name_line)
            name = name_line
            if location:
                name = name_line.replace(location, "").strip(" -–—\u2022").strip()
        
        # Second line: organization name and dates (separated by tabs)
        dates = None
        
        if len(lines) >= 2:
            org_line = lines[1]
            
            # Split by multiple spaces or tabs to separate org from dates
            org_parts = re.split(r'\s{2,}|\t', org_line.strip())
            if len(org_parts) >= 2:
                org_name = org_parts[0].strip()
                date_text = org_parts[1].strip()
                
                # Extract dates
                start_date, end_date = _extract_dates_from_text(date_text)
                if start_date:
                    dates = f"{start_date} - {end_date}" if end_date else start_date
            else:
                # Fallback: extract dates from the whole line
                start_date, end_date = _extract_dates_from_text(org_line)
                if start_date:
                    dates = f"{start_date} - {end_date}" if end_date else start_date
        
        # Remaining lines are bullets
        bullets = _bullets("\n".join(lines[2:])) if len(lines) > 2 else []
        
        items.append(ProjectItem(
            name=name or None,
            location=location,
            dates=dates,
            bullets=bullets,
            skills=[]
        ))
    
    return items

def _parse_skills(block: str) -> List[str]:
    """Handles category lines and flattens into one list"""
    skills: List[str] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        # take RHS after colon if present
        rhs = line.split(":", 1)[1] if ":" in line else line
        parts = [p.strip() for p in re.split(r"[,\|]", rhs) if p.strip()]
        skills.extend(parts)
    
    # dedupe preserve order
    seen = set()
    out = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out

def _parse_certs(block: str) -> List[str]:
    """Parse certifications with organization names"""
    out: List[str] = []
    lines = [l for l in block.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        name = lines[i].strip()
        org = None
        # Peek next if not header-y
        if i + 1 < len(lines) and not HEADER_PATTERN.match(lines[i+1].strip()):
            # If next line looks like an org (single phrase, no comma-state)
            org = lines[i+1].strip()
            i += 1
        combo = name if not org else f"{name} — {org}"
        out.append(combo)
        i += 1
    return out

def _parse_languages(block: str) -> List[str]:
    out: List[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        # Normalize '(Conversational)' etc.
        m = re.match(r"([A-Za-z\s]+)\s*\(([^)]+)\)", line)
        if m:
            lang = m.group(1).strip()
            level = m.group(2).strip().title()
            out.append(f"{lang} — {level}")
        else:
            out.append(line)
    return out

def parse_resume(path: str) -> dict:
    raw = _read_text(path)
    text = _normalize_text_preserve_tabs(raw)
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
            r.experience = _parse_experience(sections[key])
            break
    
    # Education
    if "EDUCATION" in sections:
        r.education = _parse_education(sections["EDUCATION"])
    
    # Projects
    project_skills = []
    if "PROJECTS" in sections:
        projects = _parse_projects(sections["PROJECTS"])
        r.projects = projects
        # Collect skills from projects
        for project in projects:
            project_skills.extend(project.skills)
    
    # Technical Skills / Skills
    main_skills = []
    for key in ["TECHNICAL SKILLS", "SKILLS"]:
        if key in sections:
            main_skills = _parse_skills(sections[key])
            break
    
    # Merge main skills with project skills and deduplicate
    all_skills = main_skills + project_skills
    seen = set()
    r.skills = []
    for skill in all_skills:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            r.skills.append(skill)
    
    # Certifications
    for key in ["CERTIFICATIONS & LICENSES", "CERTIFICATIONS", "LICENSES"]:
        if key in sections:
            r.certifications = _parse_certs(sections[key])
            break
    
    # Languages
    for key in ["LANGUAGES", "LANGUAGE"]:
        if key in sections:
            r.languages = _parse_languages(sections[key])
            break
    
    # Volunteer
    for key in ["VOLUNTEER EXPERIENCE", "VOLUNTEER"]:
        if key in sections:
            r.volunteer = _parse_volunteer(sections[key])
            break
    
    return r.model_dump()
