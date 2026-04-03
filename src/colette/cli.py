"""Colette CLI entry point.

Provides the ``colette`` command group with subcommands for
project submission, monitoring, approval, artifact download,
configuration, logs, and server management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import structlog

from colette import __version__

if TYPE_CHECKING:
    from rich.console import Console

logger = structlog.get_logger(__name__)

# Default API base URL for CLI commands that call the REST API.
DEFAULT_API_URL = "http://localhost:8000"


@click.group()
@click.version_option(version=__version__, prog_name="colette")
@click.option("--log-level", default="INFO", help="Logging level.")
@click.option(
    "--log-format",
    type=click.Choice(["json", "console"]),
    default="json",
    help="Log output format.",
)
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    envvar="COLETTE_API_URL",
    help="Base URL for the Colette API.",
)
@click.pass_context
def main(ctx: click.Context, log_level: str, log_format: str, api_url: str) -> None:
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
    ctx.obj["api_url"] = api_url


# ── Shared SSE progress streaming (Phase 4) ───────────────────────────


def _run_sse_loop(
    api_url: str,
    project_id: str,
    display: object,  # PipelineProgressDisplay (deferred import)
    target_console: Console,
    headers: dict[str, str],
) -> bool:
    """Run one SSE streaming session. Returns True if pipeline finished."""
    import json

    import httpx
    from rich.live import Live

    try:
        with httpx.Client(timeout=httpx.Timeout(None)) as client, client.stream(
            "GET",
            f"{api_url}/api/v1/projects/{project_id}/pipeline/events",
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            with Live(
                display.render(),  # type: ignore[union-attr]
                console=target_console,
                refresh_per_second=4,
            ) as live:
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    is_terminal = display.process_event(event)  # type: ignore[union-attr]
                    if is_terminal:
                        break
                    live.update(display.render())  # type: ignore[union-attr]
    except httpx.HTTPError as exc:
        target_console.print(f"[red bold]Error:[/red bold] Stream failed: {exc}")
        return True  # stop retrying on connection errors

    return display.is_done  # type: ignore[union-attr]


def _handle_interactive_approval(
    api_url: str,
    project_id: str,
    approval_data: dict[str, object],
    target_console: Console,
) -> bool:
    """Show the approval review panel and prompt the user.

    Returns True if approved (pipeline should resume), False otherwise.
    """
    import httpx

    from colette.cli_ui import build_approval_review_panel

    target_console.print()
    target_console.print(build_approval_review_panel(approval_data))  # type: ignore[arg-type]
    target_console.print()

    while True:
        choice = click.prompt(
            "Approve and continue?  [Y]es / [N]o",
            type=str,
            default="Y",
        ).strip().upper()

        if choice in ("Y", "YES"):
            request_id = approval_data.get("request_id", "")
            headers = {"X-API-Key": "default"}
            try:
                with httpx.Client(timeout=30) as client:
                    # Record the approval decision.
                    client.post(
                        f"{api_url}/api/v1/approvals/{request_id}/approve",
                        json={"reviewer_id": "cli-user", "comments": ""},
                        headers=headers,
                    )
                    # Resume the LangGraph pipeline.
                    resp = client.post(
                        f"{api_url}/api/v1/projects/{project_id}/pipeline/resume",
                        headers=headers,
                    )
                    resp.raise_for_status()
            except httpx.HTTPError as exc:
                target_console.print(
                    f"[red bold]Error:[/red bold] Resume failed: {exc}"
                )
                return False

            target_console.print("[green]Approved — pipeline resuming...[/green]\n")
            return True

        if choice in ("N", "NO"):
            request_id = approval_data.get("request_id", "")
            reason = click.prompt("Rejection reason", default="Rejected via CLI")
            headers = {"X-API-Key": "default"}
            try:
                with httpx.Client(timeout=30) as client:
                    client.post(
                        f"{api_url}/api/v1/approvals/{request_id}/reject",
                        json={"reviewer_id": "cli-user", "reason": reason},
                        headers=headers,
                    )
            except httpx.HTTPError:
                pass  # best-effort
            target_console.print("[yellow]Rejected — pipeline stopped.[/yellow]")
            return False

        target_console.print("[dim]Please enter Y or N.[/dim]")


def _stream_progress(
    api_url: str,
    project_id: str,
    target_console: Console,
    activity: str = "status",
) -> None:
    """Stream pipeline events via SSE and render with Rich Live.

    Connects to the SSE endpoint, creates a :class:`PipelineProgressDisplay`,
    and drives a Rich ``Live`` display until a terminal event or Ctrl+C.
    When an approval gate is hit, the Live display pauses and an
    interactive review prompt is shown inline.
    """
    from colette.cli_ui import ActivityMode, PipelineProgressDisplay

    mode = ActivityMode(activity)
    display = PipelineProgressDisplay(project_id, activity_mode=mode)
    headers = {"X-API-Key": "default"}

    while True:
        finished = _run_sse_loop(api_url, project_id, display, target_console, headers)
        if finished:
            break

        # Pipeline paused for approval — handle inline.
        approval = display.pending_approval
        if approval:
            approved = _handle_interactive_approval(
                api_url, project_id, approval, target_console
            )
            display.clear_approval()
            if approved:
                continue  # reconnect SSE — catch-up events replay progress
            break  # user rejected — stop

        break  # unexpected break without approval or terminal

    # Print final summary after Live context exits (once only).
    if display.is_done:
        target_console.print(display.render())


# ── Submit ──────────────────────────────────────────────────────────────


@main.command()
@click.option("--description", "-d", default=None, help="Project description (NL).")
@click.option("--name", "-n", default="Untitled", help="Project name.")
@click.option(
    "--activity",
    type=click.Choice(["minimal", "status", "conversation", "verbose"]),
    default="status",
    help="Agent activity display mode.",
)
@click.pass_context
def submit(ctx: click.Context, description: str | None, name: str, activity: str) -> None:
    """Submit a new project for autonomous development."""
    import httpx

    from colette.cli_ui import console, render_banner, render_error, render_success

    api_url = ctx.obj["api_url"]

    if description is None:
        render_banner()
        lines: list[str] = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        description = "\n".join(lines)

    if not description.strip():
        render_error("No description provided.")
        raise SystemExit(1)

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/api/v1/projects",
                json={"name": name, "description": description, "user_request": description},
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            data = resp.json()
            project_id = data.get("id", "?")
            render_success(f"Project created: {project_id}")
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc

    # Auto-stream progress inline (Phase 4).
    try:
        _stream_progress(api_url, project_id, console, activity=activity)
    except KeyboardInterrupt:
        console.print(
            f"\n[yellow]Interrupted.[/yellow] "
            f"Resume: [bold]colette status {project_id} --follow[/bold]"
        )


# ── Status ──────────────────────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.option("--follow", "-f", is_flag=True, help="Stream real-time progress.")
@click.option(
    "--activity",
    type=click.Choice(["minimal", "status", "conversation", "verbose"]),
    default="status",
    help="Agent activity display mode (with --follow).",
)
@click.pass_context
def status(ctx: click.Context, project_id: str, follow: bool, activity: str) -> None:
    """Check pipeline status for a project."""
    import httpx

    from colette.cli_ui import console, render_error, render_pipeline_summary

    api_url = ctx.obj["api_url"]
    headers = {"X-API-Key": "default"}

    if not follow:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{api_url}/api/v1/projects/{project_id}/pipeline",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                console.print(render_pipeline_summary(data))

                # Show LLM-blocked notice for interrupted/cancelled projects.
                proj_status = data.get("status", "")
                if proj_status in ("interrupted", "cancelled"):
                    from colette.cli_ui import render_status_notice

                    render_status_notice(proj_status, project_id)
        except httpx.HTTPError as exc:
            render_error(f"API request failed: {exc}")
            raise SystemExit(1) from exc
        return

    # Streaming mode — Rich Live display (Phase 4).
    try:
        _stream_progress(api_url, project_id, console, activity=activity)
    except KeyboardInterrupt:
        console.print(
            f"\n[yellow]Interrupted.[/yellow] "
            f"Resume: [bold]colette status {project_id} --follow[/bold]"
        )


# ── Approve / Reject ────────────────────────────────────────────────────


@main.command()
@click.argument("approval_id")
@click.option("--comment", "-c", default="", help="Approval comment.")
@click.pass_context
def approve(ctx: click.Context, approval_id: str, comment: str) -> None:
    """Approve a pending gate request."""
    import httpx

    from colette.cli_ui import render_error, render_success

    api_url = ctx.obj["api_url"]
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/api/v1/approvals/{approval_id}/approve",
                json={"reviewer_id": "cli-user", "comments": comment},
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            render_success(f"Approval {approval_id} approved.")
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


@main.command()
@click.argument("approval_id")
@click.option("--reason", "-r", default="", help="Rejection reason.")
@click.pass_context
def reject(ctx: click.Context, approval_id: str, reason: str) -> None:
    """Reject a pending gate request."""
    import httpx

    from colette.cli_ui import render_error, render_success

    api_url = ctx.obj["api_url"]
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/api/v1/approvals/{approval_id}/reject",
                json={"reviewer_id": "cli-user", "reason": reason},
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            render_success(f"Approval {approval_id} rejected.")
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


# ── Resume ─────────────────────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.pass_context
def resume(ctx: click.Context, project_id: str) -> None:
    """Resume an interrupted project (re-enables LLM calls)."""
    import httpx

    from colette.cli_ui import render_error, render_success

    api_url = ctx.obj["api_url"]
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/api/v1/projects/{project_id}/resume",
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            render_success(
                f"Project {project_id} resumed — LLM calls re-enabled.\n"
                f"  Monitor: colette status {project_id} --follow"
            )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            render_error(f"Project {project_id} not found.")
        elif exc.response.status_code == 409:
            detail = exc.response.json().get("detail", "Cannot resume.")
            render_error(detail)
        else:
            render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


# ── Cancel ─────────────────────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.pass_context
def cancel(ctx: click.Context, project_id: str) -> None:
    """Cancel a project permanently (blocks LLM calls, cannot resume)."""
    import httpx

    from colette.cli_ui import render_error, render_success

    api_url = ctx.obj["api_url"]
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/api/v1/projects/{project_id}/cancel",
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            render_success(f"Project {project_id} cancelled — LLM calls permanently blocked.")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            render_error(f"Project {project_id} not found.")
        else:
            render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


# ── Download ────────────────────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.option("--output", "-o", default=None, help="Output directory.")
@click.pass_context
def download(ctx: click.Context, project_id: str, output: str | None) -> None:
    """Download generated artifacts for a project."""
    import os
    import tempfile
    import zipfile

    import httpx

    from colette.cli_ui import console, render_error, render_success

    api_url = ctx.obj["api_url"]
    output_dir = output or f"colette-{project_id[:8]}"

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.get(
                f"{api_url}/api/v1/projects/{project_id}/artifacts/download",
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()

            # Write zip to temp, extract.
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name

            os.makedirs(output_dir, exist_ok=True)
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(output_dir)
                file_count = len(zf.namelist())

            os.unlink(tmp_path)
            render_success(f"Extracted {file_count} files to {output_dir}/")
            console.print(f"  [dim]{output_dir}[/dim]")
    except httpx.HTTPError as exc:
        render_error(f"Download failed: {exc}")
        raise SystemExit(1) from exc


# ── Config ──────────────────────────────────────────────────────────────


@main.group()
def config() -> None:
    """Manage Colette configuration."""


@config.command("show")
def config_show() -> None:
    """Display current configuration (secrets redacted)."""
    from colette.cli_ui import console, render_config_table
    from colette.config import Settings

    settings = Settings()
    console.print(render_config_table(settings.model_dump()))


@config.command("validate")
def config_validate() -> None:
    """Validate that all required settings are present."""
    from colette.cli_ui import render_error, render_success
    from colette.config import Settings

    try:
        Settings()
        render_success("Configuration is valid.")
    except Exception as exc:
        render_error(f"Configuration error: {exc}")
        raise SystemExit(1) from exc


# ── Logs ────────────────────────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.option("--stage", "-s", default=None, help="Filter by stage.")
@click.pass_context
def logs(ctx: click.Context, project_id: str, stage: str | None) -> None:
    """View pipeline logs and progress events."""
    import httpx
    from rich.table import Table

    from colette.cli_ui import console, render_error

    api_url = ctx.obj["api_url"]
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{api_url}/api/v1/projects/{project_id}/pipeline",
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            data = resp.json()

        snapshot = data.get("state_snapshot", {})
        events = snapshot.get("progress_events", [])
        errors = snapshot.get("error_log", [])

        if stage:
            events = [e for e in events if e.get("stage") == stage]
            errors = [e for e in errors if e.get("stage") == stage]

        table = Table(title=f"Logs for {project_id[:8]}...")
        table.add_column("Type", style="cyan")
        table.add_column("Stage")
        table.add_column("Detail")

        for ev in events:
            table.add_row("event", ev.get("stage", "?"), ev.get("status", ""))
        for err in errors:
            table.add_row("[red]error[/red]", err.get("stage", "?"), err.get("message", ""))

        console.print(table)
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


# ── Serve ───────────────────────────────────────────────────────────────


@main.command()
@click.option("--host", default=None, help="Bind host.")
@click.option("--port", default=None, type=int, help="Bind port.")
@click.option("--workers", default=None, type=int, help="Number of workers.")
def serve(host: str | None, port: int | None, workers: int | None) -> None:
    """Start the Colette API server."""
    import uvicorn

    from colette.config import Settings

    settings = Settings()
    uvicorn.run(
        "colette.api.app:create_app",
        factory=True,
        host=host or settings.host,
        port=port or settings.port,
        workers=workers or settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
