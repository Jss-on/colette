"""Colette CLI entry point."""

import click

from colette import __version__


@click.group()
@click.version_option(version=__version__, prog_name="colette")
def main() -> None:
    """Colette — autonomous multi-agent SDLC system."""


if __name__ == "__main__":
    main()
