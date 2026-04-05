"""Colette CLI entry point.

Provides the ``colette`` command group with subcommands for
project submission, monitoring, approval, artifact download,
configuration, logs, and server management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click
import structlog

from colette import __version__

if TYPE_CHECKING:
    from rich.console import Console

logger = structlog.get_logger(__name__)

# Default API base URL for CLI commands that call the REST API.
DEFAULT_API_URL = "http://localhost:8000"


def _version_callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Rich version output with build metadata."""
    if not value or ctx.resilient_parsing:
        return
    from colette.build_info import build_info

    info = build_info()
    click.echo(f"colette {info.version_display}")
    click.echo(f"  Python {info.python_version} on {info.platform_system}/{info.platform_machine}")
    click.echo(f"  Environment: {info.environment}")
    ctx.exit()


@click.group()
@click.option(
    "--version",
    is_flag=True,
    callback=_version_callback,
    expose_value=False,
    is_eager=True,
    help="Show version and build info.",
)
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

    from colette.build_info import build_info

    info = build_info()
    logger.info(
        "cli_started",
        version=__version__,
        environment=info.environment,
        git_sha=info.git_sha_short,
        log_level=log_level,
        log_format=log_format,
    )
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["api_url"] = api_url


# ── WebSocket progress streaming ──────────────────────────────────────


def _run_ws_loop(
    api_url: str,
    project_id: str,
    display: Any,  # PipelineProgressDisplay
    target_console: Console,
) -> bool:
    """Run one WebSocket streaming session. Returns True if finished."""
    import asyncio
    import json

    ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
    endpoint = f"{ws_url}/api/v1/projects/{project_id}/ws"

    async def _ws_stream() -> bool:
        from rich.live import Live

        try:
            import websockets
        except ImportError:
            target_console.print("[yellow]websockets not installed — falling back to SSE[/yellow]")
            return False

        try:
            async with websockets.connect(endpoint) as ws:
                with Live(
                    display.render(),
                    console=target_console,
                    refresh_per_second=8,
                ) as live:
                    async for raw in ws:
                        event = json.loads(raw)
                        if event.get("event_type") == "heartbeat":
                            continue
                        is_terminal = display.process_event(event)
                        live.update(display.render())
                        if is_terminal:
                            break
        except Exception as exc:
            target_console.print(f"[red bold]Error:[/red bold] WebSocket stream failed: {exc}")
            return True

        return bool(display.is_done)

    return asyncio.run(_ws_stream())


# ── SSE progress streaming ───────────────────────────────────────────


def _run_sse_loop(
    api_url: str,
    project_id: str,
    display: Any,  # PipelineProgressDisplay (deferred import)
    target_console: Console,
    headers: dict[str, str],
) -> bool:
    """Run one SSE streaming session. Returns True if pipeline finished."""
    import json

    import httpx
    from rich.live import Live

    try:
        with (
            httpx.Client(timeout=httpx.Timeout(None)) as client,
            client.stream(
                "GET",
                f"{api_url}/api/v1/projects/{project_id}/pipeline/events",
                headers=headers,
            ) as resp,
        ):
            resp.raise_for_status()
            with Live(
                display.render(),
                console=target_console,
                refresh_per_second=4,
            ) as live:
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    is_terminal = display.process_event(event)
                    if is_terminal:
                        break
                    live.update(display.render())
    except httpx.HTTPError as exc:
        target_console.print(f"[red bold]Error:[/red bold] Stream failed: {exc}")
        return True  # stop retrying on connection errors

    return bool(display.is_done)


def _handle_interactive_approval(
    api_url: str,
    project_id: str,
    approval_data: dict[str, object],
    target_console: Console,
) -> bool:
    """Run an interactive approval menu with drill-down views.

    Returns True if approved (pipeline should resume), False otherwise.
    """
    import httpx

    from colette.cli_review import ApprovalReviewApp

    app = ApprovalReviewApp(approval_data)
    decision = app.run()  # blocks until user decides

    if decision == "approved":
        request_id = approval_data.get("request_id", "")
        headers = {"X-API-Key": "default"}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{api_url}/api/v1/approvals/{request_id}/approve",
                    json={"reviewer_id": "cli-user", "comments": ""},
                    headers=headers,
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            target_console.print(f"[red bold]Error:[/red bold] Approve failed: {exc}")
            return False

        target_console.print("[green]Approved — pipeline resuming...[/green]\n")
        return True

    # Rejected or quit
    request_id = approval_data.get("request_id", "")
    headers = {"X-API-Key": "default"}
    try:
        with httpx.Client(timeout=30) as client:
            client.post(
                f"{api_url}/api/v1/approvals/{request_id}/reject",
                json={"reviewer_id": "cli-user", "reason": "Rejected via TUI"},
                headers=headers,
            )
    except httpx.HTTPError:
        pass
    target_console.print("[yellow]Rejected — pipeline stopped.[/yellow]")
    return False


def _stream_progress(
    api_url: str,
    project_id: str,
    target_console: Console,
    activity: str = "status",
) -> None:
    """Stream pipeline events and render with Rich Live.

    Uses WebSocket for ``conversation`` / ``verbose`` modes (real-time
    token streaming) and SSE for ``minimal`` / ``status`` modes (lower
    overhead).  When an approval gate is hit, the Live display pauses
    and an interactive review prompt is shown inline.
    """
    from colette.cli_ui import ActivityMode, PipelineProgressDisplay

    mode = ActivityMode(activity)
    display = PipelineProgressDisplay(project_id, activity_mode=mode)
    headers = {"X-API-Key": "default"}

    # Use WebSocket for modes that benefit from token streaming.
    use_ws = mode in (ActivityMode.CONVERSATION, ActivityMode.VERBOSE)

    while True:
        if use_ws:
            finished = _run_ws_loop(api_url, project_id, display, target_console)
        else:
            finished = _run_sse_loop(api_url, project_id, display, target_console, headers)
        if finished:
            break

        # Pipeline paused for approval — handle inline.
        approval = display.pending_approval
        if approval:
            approved = _handle_interactive_approval(api_url, project_id, approval, target_console)
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


# ── Approvals ──────────────────────────────────────────────────────────


@main.command()
@click.option("--project", "-p", default=None, help="Filter by project ID.")
@click.pass_context
def approvals(ctx: click.Context, project: str | None) -> None:
    """List pending approval requests."""
    import httpx
    from rich.console import Console
    from rich.table import Table

    from colette.cli_ui import render_error

    api_url = ctx.obj["api_url"]
    console = Console()
    try:
        params: dict[str, str] = {}
        if project:
            params["project_id"] = project
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{api_url}/api/v1/approvals",
                params=params,
                headers={"X-API-Key": "default"},
            )
            resp.raise_for_status()
            items = resp.json()
            if not items:
                console.print("[dim]No pending approvals.[/dim]")
                return
            table = Table(title="Pending Approvals")
            table.add_column("Request ID", style="cyan", no_wrap=True)
            table.add_column("Stage", style="green")
            table.add_column("Tier", style="yellow")
            table.add_column("Summary")
            table.add_column("Created", style="dim")
            for item in items:
                table.add_row(
                    item.get("request_id", str(item.get("id", ""))),
                    item.get("stage", ""),
                    item.get("tier", ""),
                    (item.get("context_summary", "") or "")[:60],
                    item.get("created_at", "")[:19],
                )
            console.print(table)
            console.print(
                "\n[dim]Approve:[/dim] colette approve <request-id>"
                "\n[dim]Reject:[/dim]  colette reject <request-id>"
            )
    except httpx.HTTPError as exc:
        render_error(f"API request failed: {exc}")
        raise SystemExit(1) from exc


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
