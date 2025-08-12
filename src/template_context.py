# src/template_context.py
from __future__ import annotations
from typing import Dict, List, Any

def _join_nonempty(parts: List[str], sep: str = " | ") -> str:
    return sep.join([p for p in parts if p])

def _fmt_contact(r: Dict[str, Any]) -> Dict[str, str]:
    c = r.get("contact", {}) or {}
    line1 = c.get("name") or ""
    line2 = _join_nonempty([c.get("location"), c.get("phone"), c.get("email")])
    line3 = _join_nonempty([c.get("citizenship"), c.get("clearance")], sep=" | ")
    links = _join_nonempty([c.get("linkedin"), c.get("github"), c.get("website")])
    return {
        "contact_name": line1,
        "contact_line": line2,
        "contact_status": line3,     # can be blank
        "contact_links": links,      # can be blank
    }

def _fmt_education_item(ed: Dict[str, Any]) -> Dict[str, str]:
    school_line = _join_nonempty([ed.get("school"), ed.get("location")], sep=" — ")
    degree_bits = []
    if ed.get("degree"): degree_bits.append(ed["degree"])
    if ed.get("major"): degree_bits.append(ed["major"])
    if ed.get("gpa"): degree_bits.append(f"GPA: {ed['gpa']}")
    degree_line = _join_nonempty(degree_bits, sep=" | ")
    dates_line = ed.get("dates") or ""
    conc_line = _join_nonempty(ed.get("concentrations") or [], sep=", ")
    course_line = _join_nonempty(ed.get("coursework") or [], sep=", ")
    honors_line = _join_nonempty(ed.get("honors") or [], sep=", ")
    return {
        "school_line": school_line,
        "degree_line": degree_line,
        "dates_line": dates_line,
        "concentrations_line": conc_line,
        "coursework_line": course_line,
        "honors_line": honors_line,
        "bullets": ed.get("bullets") or [],
    }

def _fmt_experience_item(e: Dict[str, Any]) -> Dict[str, Any]:
    header1 = _join_nonempty([e.get("company"), e.get("location")], sep=" — ")
    dates = " – ".join([p for p in [e.get("start_date"), e.get("end_date") or "Present"] if p])
    header2 = _join_nonempty([e.get("title"), dates], sep="     ")
    return {
        "header_company": header1,
        "header_title_dates": header2,
        "bullets": e.get("bullets") or [],
        "priority": e.get("priority"),
    }

def _fmt_project_item(p: Dict[str, Any]) -> Dict[str, Any]:
    header = _join_nonempty(
        [p.get("name"), p.get("location")], sep=" — "
    )
    if p.get("dates"):
        header = _join_nonempty([header, p["dates"]], sep="     ")
    return {
        "header": header,
        "bullets": p.get("bullets") or [],
        "priority": p.get("priority"),
    }

def _fmt_cert_item(c: Dict[str, Any]) -> str:
    parts = [c.get("name")]
    if c.get("year"): parts.append(f"({c['year']})")
    if c.get("organization"): parts.append(f"— {c['organization']}")
    return " ".join([p for p in parts if p])

def _skills_matrix_lines(matrix: Dict[str, List[str]]) -> List[str]:
    lines = []
    for cat, items in (matrix or {}).items():
        line = f"{cat}: " + ", ".join(items)
        lines.append(line)
    return lines

def build_template_context(resume: Dict[str, Any]) -> Dict[str, Any]:
    """Return a flat, template-friendly context so the docx has tiny Jinja tags."""
    ctx = {"resume": resume}  # keep original available just in case

    # Contact
    ctx.update(_fmt_contact(resume))

    # Summary
    ctx["has_summary"] = bool(resume.get("summary"))
    ctx["summary_text"] = resume.get("summary") or ""

    # Education
    ed_items = [ _fmt_education_item(ed) for ed in (resume.get("education") or []) ]
    ctx["has_education"] = len(ed_items) > 0
    ctx["education_items"] = ed_items

    # Experience
    ex_items = [ _fmt_experience_item(e) for e in (resume.get("experience") or []) ]
    ctx["has_experience"] = len(ex_items) > 0
    ctx["experience_items"] = ex_items

    # Projects
    pj_items = [ _fmt_project_item(p) for p in (resume.get("projects") or []) ]
    ctx["has_projects"] = len(pj_items) > 0
    ctx["project_items"] = pj_items

    # Volunteer (reuse project shape)
    vol_items = [ _fmt_project_item(v) for v in (resume.get("volunteer") or []) ]
    ctx["has_volunteer"] = len(vol_items) > 0
    ctx["volunteer_items"] = vol_items

    # Skills (flat + categorized with auto-pick)
    skills = resume.get("skills") or []
    skills_matrix = resume.get("skills_matrix") or {}

    ctx["has_skills"] = bool(skills) or bool(skills_matrix)

    # If we have categories, prefer matrix display
    if skills_matrix:
        ctx["skills_display_type"] = "matrix"
        ctx["skills_matrix_lines"] = _skills_matrix_lines(skills_matrix)
        ctx["skills_line"] = ""  # flat line not used
    elif skills:
        ctx["skills_display_type"] = "flat"
        ctx["skills_line"] = ", ".join(skills)
        ctx["skills_matrix_lines"] = []
    else:
        ctx["skills_display_type"] = "none"
        ctx["skills_line"] = ""
        ctx["skills_matrix_lines"] = []

    # Certifications (structured -> lines)
    certs = resume.get("certifications") or []
    cert_lines = [ _fmt_cert_item(c if isinstance(c, dict) else {"name": c}) for c in certs ]
    ctx["has_certifications"] = len(cert_lines) > 0
    ctx["certification_lines"] = cert_lines

    # Languages / misc
    langs = resume.get("languages") or []
    ctx["has_languages"] = len(langs) > 0
    ctx["languages_line"] = ", ".join(langs)

    # Optional sections
    for key in ["honors", "interests", "affiliations", "publications", "awards"]:
        vals = resume.get(key) or []
        ctx[f"has_{key}"] = len(vals) > 0
        ctx[f"{key}_lines"] = vals if isinstance(vals, list) else [str(vals)]

    return ctx
