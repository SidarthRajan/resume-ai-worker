# src/exporter.py
from __future__ import annotations
import json, os
from typing import Dict
from docxtpl import DocxTemplate
from .template_context import build_template_context

def export_docx(tailored_json_path: str, template_path: str, out_path: str):
    data: Dict = json.load(open(tailored_json_path, "r", encoding="utf-8"))
    ctx = build_template_context(data)   # << all precomputed, short placeholders
    doc = DocxTemplate(template_path)
    doc.render(ctx)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)
