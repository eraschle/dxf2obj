# Datei: dxf_element_mapper/main.py
from pathlib import Path

import click

import config


@click.command()
@click.argument(
    "dxf_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.argument(
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, writable=True),
    help="Pfad für die Ausgabe (JSON)",
)
def main(dxf_path: Path, config_path: Path, output_path: Path | None = None):
    click.echo(click.style(f"Lade Elementdaten von: {config_path}", fg="cyan"))
    processor_config = config.load_processor_config(config_path)
    processor = Processor(processor_config)


if __name__ == "__main__":
    main()
