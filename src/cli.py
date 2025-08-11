# src/cli.py
import click, json, os
from .parser import parse_resume

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

if __name__ == "__main__":
    cli()
