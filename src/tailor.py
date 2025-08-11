# src/tailor.py
from __future__ import annotations
import json, os
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from pydantic import ValidationError
from openai import OpenAI
from .schema import Resume

PROMPTS_DIR = Path(__file__).parent / "prompts"

SYSTEM_MSG = (
    "You are a precise resume editor. "
    "Rewrite the provided resume to better align with the job description. "
    "Absolute rules: Do not invent employment, degrees, companies, or dates. "
    "Only rephrase or reprioritize existing content. Maintain truth. "
    "Return a single JSON object that strictly matches the provided schema."
)

# Keep prompt payload smaller (cheap + safer for context limits)
def _shrink_for_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    d = json.loads(json.dumps(data))  # deep copy
    # cap bullets per item and skills length; adjust as needed
    for item in d.get("experience", []):
        if isinstance(item.get("bullets"), list):
            item["bullets"] = item["bullets"][:6]
    for item in d.get("projects", []):
        if isinstance(item.get("bullets"), list):
            item["bullets"] = item["bullets"][:4]
    if isinstance(d.get("skills"), list):
        d["skills"] = d["skills"][:40]
    if isinstance(d.get("certifications"), list):
        d["certifications"] = d["certifications"][:10]
    if isinstance(d.get("languages"), list):
        d["languages"] = d["languages"][:10]
    if isinstance(d.get("volunteer"), list):
        for item in d["volunteer"]:
            if isinstance(item.get("bullets"), list):
                item["bullets"] = item["bullets"][:3]
    # summary length hint (the model will rewrite; we just keep context small)
    if d.get("summary"):
        d["summary"] = d["summary"][:1200]
    return d

def _schema_json() -> str:
    # Provide the model with the expected JSON Schema to reduce drift
    # (Using Pydantic v2 schema)
    schema = Resume.model_json_schema()
    return json.dumps(schema, ensure_ascii=False)

def _client() -> OpenAI:
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing. Add it to .env")
    return OpenAI(api_key=key)

def _build_user_prompt(parsed_resume: Dict[str, Any], job_desc: str) -> str:
    return (
        "TASK:\n"
        "Rewrite the resume JSON to align with the job description while preserving truth. "
        "Rephrase text, reorder bullets for relevance, and prioritize JD-aligned content. "
        "Do NOT invent new employers, degrees, dates, or technologies that weren't present.\n\n"
        "INPUTS:\n"
        "1) job_description:\n"
        f"{job_desc}\n\n"
        "2) parsed_resume_json:\n"
        f"{json.dumps(parsed_resume, ensure_ascii=False)}\n\n"
        "OUTPUT FORMAT:\n"
        "Return ONLY a JSON object that validates against the provided JSON Schema. "
        "No markdown, no commentary.\n\n"
        "JSON_SCHEMA:\n"
        f"{_schema_json()}\n"
    )

def _call_model(prompt: str) -> str:
    client = _client()
    # If your SDK supports response_format=json, you can uncomment:
    # response_format = {"type": "json_object"}
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        # response_format=response_format,
    )
    return resp.choices[0].message.content.strip()

def rewrite_sections_single_call(parsed_json_path: str, jd_path: str) -> Dict[str, Any]:
    parsed = json.load(open(parsed_json_path, "r", encoding="utf-8"))
    jd = open(jd_path, "r", encoding="utf-8").read()

    # Ensure shape before editing
    base = Resume.model_validate(parsed).model_dump()
    compact = _shrink_for_prompt(base)
    prompt = _build_user_prompt(compact, jd)

    raw = _call_model(prompt)

    # Try parse & validate; retry once with corrective instruction if needed
    def _validate_or_none(s: str):
        try:
            data = json.loads(s)
            return Resume.model_validate(data).model_dump()
        except (json.JSONDecodeError, ValidationError):
            return None

    result = _validate_or_none(raw)
    if result is not None:
        return result

    # Retry with corrective nudge
    corrective = (
        "Previous output failed JSON validation. "
        "Strictly output a single valid JSON object that matches the schema. "
        "Do not include any text outside of the JSON."
    )
    raw2 = _call_model(
        prompt + "\n\nCORRECTION:\n" + corrective
    )
    result2 = _validate_or_none(raw2)
    if result2 is not None:
        return result2

    # Fall back to original parsed if still invalid (never block pipeline)
    return base

# Backward compatibility
def rewrite_sections(parsed_json_path: str, jd_path: str) -> dict:
    return rewrite_sections_single_call(parsed_json_path, jd_path)
