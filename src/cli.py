# src/cli.py
import click, json, os
from .parser import parse_resume
from .tailor import rewrite_sections_single_call
from .exporter import export_docx

@click.group()
def cli(): pass

@cli.command()
@click.option('--resume', required=True)
@click.option('--out', required=True)
def parse(resume, out):
    data = parse_resume(resume)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    click.echo(f"Wrote {out}")

@cli.command()
@click.option('--parsed', required=True)
@click.option('--jd', required=True)
@click.option('--out', required=True)
def tailor(parsed, jd, out):
    data = rewrite_sections_single_call(parsed, jd)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    click.echo(f"Wrote {out}")

@cli.command()
@click.option('--tailored', required=True)
@click.option('--template', required=True)
@click.option('--out', required=True)
def export(tailored, template, out):
    export_docx(tailored, template, out)
    click.echo(f"Wrote {out}")

if __name__ == "__main__":
    cli()
