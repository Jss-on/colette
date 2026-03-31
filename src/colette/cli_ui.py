"""Rich terminal rendering for the Colette CLI (NFR-USA-001/003)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()

# ── Pipeline stage definitions ────────────────────────────────────────

PIPELINE_STAGES = (
    "requirements",
    "design",
    "implementation",
    "testing",
    "deployment",
    "monitoring",
)

_STAGE_LABELS: dict[str, str] = {
    "requirements": "Requirements",
    "design": "Design",
    "implementation": "Implementation",
    "testing": "Testing",
    "deployment": "Deployment",
    "monitoring": "Monitoring",
}


@dataclass(frozen=True)
class StageState:
    """Immutable snapshot of a single pipeline stage's state."""

    name: str
    status: str = "pending"
    elapsed_seconds: float = 0.0
    tokens_used: int = 0
    agent: str = ""
    message: str = ""


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
            "interrupted": "magenta",
            "cancelled": "dim red",
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
    color = {
        "completed": "green",
        "running": "yellow",
        "failed": "red",
        "interrupted": "magenta",
        "cancelled": "dim red",
    }.get(status, "white")
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


def render_status_notice(status: str, project_id: str) -> None:
    """Print a notice when a project is in a non-active state."""
    if status == "interrupted":
        console.print(
            f"[magenta bold]Status: interrupted (LLM calls blocked)[/magenta bold]\n"
            f"  Use [bold]colette resume {project_id}[/bold] to reactivate."
        )
    elif status == "cancelled":
        console.print(
            "[dim red bold]Status: cancelled (LLM calls blocked, cannot resume)[/dim red bold]"
        )


def render_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red bold]Error:[/red bold] {message}")


def render_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green bold]OK:[/green bold] {message}")


# ── Phase 4: Inline progress display ─────────────────────────────────

_STATUS_ICONS: dict[str, str] = {
    "completed": "[green]✓[/green]",
    "running": "[yellow]>[/yellow]",
    "failed": "[red]✗[/red]",
    "pending": "[dim]-[/dim]",
    "interrupted": "[magenta]![/magenta]",
}


def build_progress_renderable(
    stages: tuple[StageState, ...],
    error_message: str = "",
) -> Table:
    """Build a Rich table showing live pipeline stage progression."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("icon", width=3, no_wrap=True)
    table.add_column("stage")
    table.add_column("elapsed", justify="right", style="dim")

    for stage in stages:
        icon = _STATUS_ICONS.get(stage.status, " ")
        label = _STAGE_LABELS.get(stage.name, stage.name)
        elapsed = f"({stage.elapsed_seconds:.0f}s)" if stage.elapsed_seconds else ""

        if stage.status == "running" and (stage.agent or stage.message):
            agent = escape(stage.agent)
            msg = escape(stage.message)
            activity = " — "
            if agent and msg:
                activity += f"{agent}: {msg}"
            else:
                activity += agent or msg
            table.add_row(icon, f"{label}{activity}", elapsed)
        else:
            table.add_row(icon, label, elapsed)

    if error_message:
        table.add_row("", f"[red]Error: {escape(error_message)}[/red]", "")

    return table


def build_summary_panel(
    stages: tuple[StageState, ...],
    project_id: str,
    final_status: str,
    error_message: str = "",
) -> Panel:
    """Build a final summary panel after pipeline completion."""
    color = {"completed": "green", "failed": "red"}.get(final_status, "yellow")
    completed_count = sum(1 for s in stages if s.status == "completed")
    total_tokens = sum(s.tokens_used for s in stages)
    total_elapsed = sum(s.elapsed_seconds for s in stages)

    content = (
        f"[bold]Project:[/bold] {escape(project_id)}\n"
        f"[bold]Status:[/bold] [{color}]{final_status}[/{color}]\n"
        f"[bold]Stages:[/bold] {completed_count}/{len(stages)} completed\n"
        f"[bold]Tokens:[/bold] {total_tokens:,}\n"
        f"[bold]Elapsed:[/bold] {total_elapsed:.1f}s"
    )
    if error_message:
        content += f"\n[bold]Error:[/bold] [red]{escape(error_message)}[/red]"

    return Panel(content, title="Pipeline Summary", border_style=color)


class PipelineProgressDisplay:
    """Live pipeline progress state machine (Phase 4).

    Accepts SSE event dicts via :meth:`process_event`, tracks stage
    states immutably, and produces Rich renderables via :meth:`render`.
    """

    def __init__(self, project_id: str, target_console: Console | None = None) -> None:
        self._project_id = project_id
        self._stages = tuple(StageState(name=n) for n in PIPELINE_STAGES)
        self._error = ""
        self._final_status = ""

    # ── Read-only properties ──────────────────────────────────────────

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def stages(self) -> tuple[StageState, ...]:
        return self._stages

    @property
    def is_done(self) -> bool:
        return self._final_status != ""

    @property
    def final_status(self) -> str:
        return self._final_status

    @property
    def error_message(self) -> str:
        return self._error

    # ── Event processing ──────────────────────────────────────────────

    def _stage_index(self, name: str) -> int | None:
        """Return index for a known stage, or None."""
        for i, s in enumerate(self._stages):
            if s.name == name:
                return i
        return None

    def _replace_stage(self, idx: int, **kwargs: Any) -> None:
        """Immutably rebuild the stages tuple with one replacement."""
        updated = replace(self._stages[idx], **kwargs)
        self._stages = (*self._stages[:idx], updated, *self._stages[idx + 1 :])

    def process_event(self, event: dict[str, Any]) -> bool:
        """Process an SSE event dict. Returns True on terminal event."""
        etype = event.get("event_type", "")
        stage = event.get("stage", "")
        idx = self._stage_index(stage) if stage else None

        if etype == "stage_started" and idx is not None:
            self._replace_stage(idx, status="running", agent="", message="")

        elif etype == "stage_completed" and idx is not None:
            self._replace_stage(
                idx,
                status="completed",
                elapsed_seconds=event.get("elapsed_seconds", 0.0),
                tokens_used=event.get("tokens_used", 0),
                agent="",
                message="",
            )

        elif etype == "stage_failed" and idx is not None:
            self._replace_stage(idx, status="failed")
            self._error = event.get("message", "Unknown error")

        elif etype == "agent_started" and idx is not None:
            self._replace_stage(
                idx,
                agent=event.get("agent", ""),
                message=event.get("message", ""),
            )

        elif etype == "agent_completed" and idx is not None:
            self._replace_stage(idx, agent="", message="")

        elif etype == "agent_error":
            self._error = event.get("message", "Agent error")

        elif etype == "gate_failed" and idx is not None:
            self._replace_stage(idx, status="failed")
            self._error = event.get("message", "Gate failed")

        elif etype in ("pipeline_completed", "complete"):
            self._final_status = "completed"
            return True

        elif etype == "pipeline_failed":
            self._final_status = "failed"
            self._error = event.get("message", "Pipeline failed")
            return True

        return False

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> Table | Panel:
        """Return the current renderable — progress table or summary."""
        if self.is_done:
            return build_summary_panel(
                self._stages, self._project_id, self._final_status, self._error
            )
        return build_progress_renderable(self._stages, self._error)
