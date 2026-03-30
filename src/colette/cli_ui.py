"""Rich terminal rendering for the Colette CLI (NFR-USA-001/003)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


def render_banner() -> None:
    """Print the Colette welcome banner."""
    console.print(
        Panel(
            "[bold]Colette[/bold] — autonomous multi-agent SDLC system\n"
            "Enter your project description below. Press Ctrl+D (or Ctrl+Z on Windows) to submit.",
            title="Welcome",
            border_style="blue",
        )
    )


def render_progress_table(events: list[dict[str, Any]]) -> Table:
    """Build a Rich table showing pipeline stage progression."""
    table = Table(title="Pipeline Progress", show_lines=True)
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Elapsed (s)", justify="right")
    table.add_column("Tokens", justify="right")

    for ev in events:
        status = ev.get("status", "unknown")
        style = {
            "completed": "green",
            "running": "yellow",
            "failed": "red",
            "pending": "dim",
        }.get(status, "")
        table.add_row(
            ev.get("stage", "?"),
            f"[{style}]{status}[/{style}]" if style else status,
            str(ev.get("elapsed_seconds", "")),
            str(ev.get("tokens_used", "")),
        )
    return table


def render_approval_prompt(approval: dict[str, Any]) -> Panel:
    """Render an approval request for interactive review."""
    content = (
        f"[bold]Stage:[/bold] {approval.get('stage', '?')}\n"
        f"[bold]Tier:[/bold] {approval.get('tier', '?')}\n"
        f"[bold]Risk:[/bold] {approval.get('risk_assessment', 'N/A')}\n\n"
        f"[bold]Context:[/bold]\n{approval.get('context_summary', '')}\n\n"
        f"[bold]Proposed Action:[/bold]\n{approval.get('proposed_action', '')}"
    )
    return Panel(content, title="Approval Required", border_style="yellow")


def render_pipeline_summary(data: dict[str, Any]) -> Panel:
    """Render a final pipeline summary."""
    status = data.get("status", "unknown")
    color = {"completed": "green", "running": "yellow", "failed": "red"}.get(status, "white")
    content = (
        f"[bold]Project:[/bold] {data.get('project_id', '?')}\n"
        f"[bold]Status:[/bold] [{color}]{status}[/{color}]\n"
        f"[bold]Stage:[/bold] {data.get('current_stage', '?')}\n"
        f"[bold]Tokens:[/bold] {data.get('total_tokens', 0):,}\n"
        f"[bold]Thread:[/bold] {data.get('thread_id', '?')}"
    )
    return Panel(content, title="Pipeline Summary", border_style=color)


def render_artifact_tree(files: list[dict[str, Any]]) -> Tree:
    """Render a file tree of generated artifacts."""
    tree = Tree("[bold]Generated Files[/bold]")
    for f in files:
        path = f.get("path", "unknown")
        size = f.get("size_bytes", 0)
        lang = f.get("language", "")
        label = f"{path}"
        if lang:
            label += f" [{lang}]"
        if size:
            label += f" ({size:,} bytes)"
        tree.add(label)
    return tree


def render_config_table(settings: dict[str, Any], *, redact_secrets: bool = True) -> Table:
    """Render current configuration as a table."""
    table = Table(title="Colette Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    secret_keys = {"api_key", "password", "secret", "token", "hash"}
    for key, value in sorted(settings.items()):
        display = str(value)
        if redact_secrets and any(s in key.lower() for s in secret_keys):
            display = "***"
        table.add_row(key, display)
    return table


def render_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red bold]Error:[/red bold] {message}")


def render_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green bold]OK:[/green bold] {message}")
