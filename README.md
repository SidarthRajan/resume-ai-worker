# Resume AI Tailor (Backend MVP)

Pipeline:
1) Parse resume (PDF/DOCX) -> normalized JSON
2) Tailor JSON with OpenAI prompts against a job description
3) Export tailored JSON -> DOCX via docxtpl template

## Quickstart
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # add your key later

## Commands (will work after later steps)
python -m src.cli parse --resume tests/sample_resume.docx --out tests/parsed.json
python -m src.cli tailor --parsed tests/parsed.json --jd tests/job.txt --out tests/tailored.json
python -m src.cli export --tailored tests/tailored.json --template src/templates/resume.docx --out output/tailored_resume.docx
