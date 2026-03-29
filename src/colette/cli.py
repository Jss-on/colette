"""Colette CLI entry point.

Provides the ``colette`` command group.  Logging and tracing are
initialised before any subcommand runs.
"""

from __future__ import annotations

import click
import structlog

from colette import __version__

logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="colette")
@click.option("--log-level", default="INFO", help="Logging level.")
@click.option(
    "--log-format",
    type=click.Choice(["json", "console"]),
    default="json",
    help="Log output format.",
)
@click.pass_context
def main(ctx: click.Context, log_level: str, log_format: str) -> None:
    """Colette -- autonomous multi-agent SDLC system."""
    from colette.observability.logging import configure_logging

    configure_logging(log_level=log_level, log_format=log_format)
    logger.info(
        "cli_started",
        version=__version__,
        log_level=log_level,
        log_format=log_format,
    )
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level


if __name__ == "__main__":
    main()
