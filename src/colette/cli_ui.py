"""Rich terminal rendering for the Colette CLI (NFR-USA-001/003)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from colette import __version__
from colette.orchestrator.agent_presence import (
    AgentPresence,
    AgentPresenceTracker,
    AgentState,
    ConversationEntry,
)

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


def render_approval_prompt(approval: dict[str, Any]) -> Text:
    """Render an inline approval prompt (Claude Code-style)."""
    stage = approval.get("stage", "?")
    confidence = approval.get("confidence_score", "")
    risk = approval.get("risk_assessment", "")

    t = Text()
    t.append("  approval required", style="bold")
    t.append(f" - {stage} gate\n\n", style="bold")

    t.append(f"  stage: {stage}", style="dim")
    if confidence:
        t.append(f"  confidence: {confidence}", style="dim")
    if risk:
        t.append(f"  risk: {risk}", style="dim")
    t.append("\n\n")
    t.append('  press enter to review, or type "approve" / "reject"', style="dim")
    return t


def build_approval_review_panel(event_data: dict[str, Any]) -> Panel:
    """Build a compact summary panel with key metrics for the interactive menu."""
    stage = event_data.get("stage", "?")
    tier = event_data.get("tier", "?")
    score = event_data.get("confidence_score")
    summary = event_data.get("handoff_summary", {})

    lines: list[str] = [
        f"[bold yellow]Stage:[/bold yellow]  {_STAGE_LABELS.get(stage, stage)}",
        f"[bold yellow]Tier:[/bold yellow]   {tier}",
    ]
    if score is not None:
        lines.append(f"[bold yellow]Score:[/bold yellow]  {score:.2f}")
    lines.append("")

    # Show quick counts per section.
    s = summary.get("stage", stage)
    if s == "requirements":
        lines.append(f"  User Stories:      {len(summary.get('user_stories', []))}")
        lines.append(f"  NFRs:              {len(summary.get('nfrs', []))}")
        lines.append(f"  Tech Constraints:  {len(summary.get('tech_constraints', []))}")
        cs = summary.get("completeness_score", 0)
        if cs:
            lines.append(f"  Completeness:      {cs:.0%}")
    elif s == "design":
        lines.append(f"  API Endpoints:     {len(summary.get('endpoints', []))}")
        lines.append(f"  DB Entities:       {len(summary.get('db_entities', []))}")
        lines.append(f"  UI Components:     {len(summary.get('ui_components', []))}")
        lines.append(f"  ADRs:              {len(summary.get('adrs', []))}")
        tech = summary.get("tech_stack", {})
        if tech:
            stack_str = ", ".join(f"{r}={v}" for r, v in list(tech.items())[:4])
            lines.append(f"  Tech Stack:        {stack_str}")
    elif s == "implementation":
        lines.append(f"  Files Generated:   {summary.get('file_count', 0)}")
        lines.append(f"  Packages:          {len(summary.get('packages', []))}")
    elif s == "testing":
        lines.append(f"  Test Files:        {len(summary.get('test_files', []))}")
        lines.append(f"  Line Coverage:     {summary.get('line_coverage', 0):.0f}%")
        lines.append(f"  Security Findings: {len(summary.get('security_findings', []))}")
    elif s == "deployment":
        lines.append(f"  Deploy Target:     {summary.get('deploy_target', '?')}")
        lines.append(f"  Config Files:      {len(summary.get('deployment_configs', []))}")

    return Panel(
        "\n".join(lines),
        title="Review Required",
        border_style="yellow",
    )


# ── Interactive approval: drill-down renderers ────────────────────────


def build_review_menu(summary: dict[str, Any]) -> str:
    """Build the numbered menu string based on which sections have data."""
    stage = summary.get("stage", "")
    items: list[str] = []
    idx = 1

    for key, label in _review_menu_items(stage):
        data = summary.get(key, [] if key != "tech_stack" else {})
        count = len(data) if isinstance(data, list | dict) else 0
        if count or key == "architecture_preview":
            if count:
                items.append(f"  [bold cyan][{idx}][/bold cyan] {label} ({count})")
            else:
                items.append(f"  [bold cyan][{idx}][/bold cyan] {label}")
            idx += 1

    items.append("")
    items.append("  [bold green][A][/bold green] Approve   [bold red][R][/bold red] Reject")
    return "\n".join(items)


def _review_menu_items(stage: str) -> list[tuple[str, str]]:
    """Return (data_key, label) pairs for the given stage."""
    if stage == "requirements":
        return [
            ("user_stories", "User Stories"),
            ("nfrs", "Non-Functional Requirements"),
            ("tech_constraints", "Tech Constraints"),
        ]
    if stage == "design":
        return [
            ("endpoints", "API Endpoints"),
            ("db_entities", "DB Entities"),
            ("ui_components", "UI Components"),
            ("tech_stack", "Tech Stack"),
            ("adrs", "Architecture Decisions"),
            ("openapi_spec", "OpenAPI Spec"),
            ("architecture_summary", "Architecture Document"),
            ("security_design", "Security Design"),
        ]
    if stage == "implementation":
        return [
            ("generated_files", "Source Code Files"),
            ("files", "File Change Summary"),
            ("packages", "Packages"),
        ]
    if stage == "testing":
        return [
            ("generated_files", "Test Source Files"),
            ("test_files", "Test Results Summary"),
            ("security_findings", "Security Findings"),
        ]
    if stage == "deployment":
        return [
            ("generated_files", "Deploy Config Files"),
            ("deployment_configs", "Deployment Targets"),
        ]
    return []


def resolve_menu_choice(choice: str, summary: dict[str, Any]) -> str | None:
    """Map a numeric menu choice to the data key, or None if invalid."""
    stage = summary.get("stage", "")
    items = _review_menu_items(stage)
    visible: list[str] = []
    for key, _label in items:
        data = summary.get(key, [] if key != "tech_stack" else {})
        if isinstance(data, str) or (isinstance(data, list | dict) and data):
            visible.append(key)
    try:
        idx = int(choice) - 1
    except ValueError:
        return None
    return visible[idx] if 0 <= idx < len(visible) else None


def render_detail_view(key: str, summary: dict[str, Any]) -> Panel | Table:
    """Render a drill-down detail view for a specific section."""
    data = summary.get(key)
    label = key.replace("_", " ").title()

    if key == "endpoints":
        return _render_endpoints_table(data or [])
    if key == "db_entities":
        return _render_entities_table(data or [])
    if key == "ui_components":
        return _render_components_table(data or [])
    if key == "adrs":
        return _render_adrs_panel(data or [])
    if key == "tech_stack":
        return _render_tech_stack_table(data or {})
    if key == "user_stories":
        return _render_user_stories_table(data or [])
    if key == "nfrs":
        return _render_nfrs_table(data or [])
    if key == "tech_constraints":
        return _render_constraints_table(data or [])
    if key == "files":
        return _render_files_table(data or [])
    if key == "test_files":
        return _render_files_table(data or [])
    if key == "security_findings":
        return _render_security_findings_table(data or [])
    if key == "deployment_configs":
        return _render_files_table(data or [])
    if key == "packages":
        return _render_simple_list(label, data or [])
    # Document artifacts (full text)
    if key in ("openapi_spec", "architecture_summary", "security_design"):
        return _render_document(label, str(data or ""), key)
    # Source code files (GeneratedFile dicts with content)
    if key == "generated_files":
        return _render_generated_files_index(data or [])

    return Panel(escape(str(data or "")), title=label, border_style="blue")


# ── Detail renderers ─────────────────────────────────────────────────


def _render_endpoints_table(endpoints: list[dict[str, Any]]) -> Table:
    table = Table(title="API Endpoints", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Method", style="bold cyan", width=7)
    table.add_column("Path", style="green")
    table.add_column("Summary")
    table.add_column("Auth", width=4, justify="center")
    for i, ep in enumerate(endpoints, 1):
        auth = "[green]Y[/green]" if ep.get("auth_required", True) else "[dim]N[/dim]"
        table.add_row(
            str(i),
            ep.get("method", "?"),
            ep.get("path", "?"),
            escape(ep.get("summary", "")),
            auth,
        )
    return table


def _render_entities_table(entities: list[dict[str, Any]]) -> Table:
    table = Table(title="DB Entities", show_lines=True)
    table.add_column("Entity", style="bold cyan")
    table.add_column("Fields")
    table.add_column("Indexes", style="dim")
    table.add_column("Relationships", style="dim")
    for ent in entities:
        fields = ent.get("fields", [])
        field_strs = [f"{f.get('name', '?')}: {f.get('type', '?')}" for f in fields[:8]]
        if len(fields) > 8:
            field_strs.append(f"... +{len(fields) - 8} more")
        indexes = ", ".join(ent.get("indexes", [])) or "-"
        rels = ", ".join(ent.get("relationships", [])) or "-"
        table.add_row(ent.get("name", "?"), "\n".join(field_strs), indexes, rels)
    return table


def _render_components_table(components: list[dict[str, Any]]) -> Table:
    table = Table(title="UI Components", show_lines=True)
    table.add_column("Component", style="bold cyan")
    table.add_column("Description")
    table.add_column("Route", style="dim")
    table.add_column("Children", style="dim")
    for comp in components:
        route = comp.get("route") or "-"
        children = ", ".join(comp.get("children", [])) or "-"
        table.add_row(
            comp.get("name", "?"),
            escape(comp.get("description", "")),
            route,
            children,
        )
    return table


def _render_adrs_panel(adrs: list[dict[str, Any]]) -> Panel:
    lines: list[str] = []
    for adr in adrs:
        adr_id = escape(adr.get("id", "?"))
        adr_title = escape(adr.get("title", "?"))
        lines.append(f"[bold cyan]{adr_id}: {adr_title}[/bold cyan]")
        lines.append(f"  [bold]Status:[/bold] {adr.get('status', '?')}")
        ctx = adr.get("context", "")
        if ctx:
            lines.append(f"  [bold]Context:[/bold] {escape(ctx[:200])}")
        dec = adr.get("decision", "")
        if dec:
            lines.append(f"  [bold]Decision:[/bold] {escape(dec[:200])}")
        alts = adr.get("alternatives", [])
        if alts:
            lines.append("  [bold]Alternatives:[/bold]")
            for alt in alts:
                lines.append(f"    - {escape(alt)}")
        lines.append("")
    return Panel("\n".join(lines), title="Architecture Decisions", border_style="blue")


def _render_tech_stack_table(tech: dict[str, Any]) -> Table:
    table = Table(title="Tech Stack")
    table.add_column("Role", style="bold cyan")
    table.add_column("Technology", style="green")
    for role, choice in tech.items():
        table.add_row(role, escape(str(choice)))
    return table


def _render_user_stories_table(stories: list[dict[str, Any]]) -> Table:
    table = Table(title="User Stories", show_lines=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Title", style="bold")
    table.add_column("Priority", width=8)
    table.add_column("Acceptance Criteria")
    for s in stories:
        ac = s.get("acceptance_criteria", [])
        ac_str = "\n".join(f"- {escape(c)}" for c in ac[:5])
        if len(ac) > 5:
            ac_str += f"\n... +{len(ac) - 5} more"
        table.add_row(
            s.get("id", "?"),
            escape(s.get("title", "?")),
            s.get("priority", "?"),
            ac_str,
        )
    return table


def _render_nfrs_table(nfrs: list[dict[str, Any]]) -> Table:
    table = Table(title="Non-Functional Requirements", show_lines=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Category", style="cyan")
    table.add_column("Description")
    table.add_column("Target", style="dim")
    for n in nfrs:
        table.add_row(
            n.get("id", "?"),
            n.get("category", "?"),
            escape(n.get("description", "")),
            n.get("target", "") or "-",
        )
    return table


def _render_constraints_table(constraints: list[dict[str, Any]]) -> Table:
    table = Table(title="Tech Constraints", show_lines=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Description")
    table.add_column("Rationale", style="dim")
    for c in constraints:
        table.add_row(
            c.get("id", "?"),
            escape(c.get("description", "")),
            escape(c.get("rationale", "")),
        )
    return table


def _render_files_table(files: list[dict[str, Any]]) -> Table:
    table = Table(title="Files")
    table.add_column("#", style="dim", width=3)
    table.add_column("Path", style="green")
    table.add_column("Language", style="dim", width=12)
    for i, f in enumerate(files, 1):
        path = f.get("path", "?") if isinstance(f, dict) else str(f)
        lang = f.get("language", "") if isinstance(f, dict) else ""
        table.add_row(str(i), escape(path), lang)
    return table


def _render_security_findings_table(findings: list[dict[str, Any]]) -> Table:
    table = Table(title="Security Findings", show_lines=True)
    table.add_column("Severity", style="bold")
    table.add_column("Category")
    table.add_column("Description")
    for f in findings:
        sev = f.get("severity", "?")
        severity_styles = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "dim",
        }
        sev_style = severity_styles.get(sev.lower(), "")
        table.add_row(
            f"[{sev_style}]{sev}[/{sev_style}]" if sev_style else sev,
            f.get("category", "?"),
            escape(f.get("description", "")),
        )
    return table


def _render_simple_list(title: str, items: list[Any]) -> Panel:
    lines = [f"  - {escape(str(item))}" for item in items]
    return Panel("\n".join(lines) or "[dim]None[/dim]", title=title, border_style="blue")


# ── Document artifact viewers ────────────────────────────────────────


def _render_document(title: str, text: str, key: str) -> Panel:
    """Render a full text artifact with optional syntax highlighting."""
    from rich.syntax import Syntax

    if not text.strip():
        return Panel("[dim]Empty[/dim]", title=title, border_style="blue")

    if key == "openapi_spec":
        try:
            content: Any = Syntax(text, "json", theme="monokai", word_wrap=True)
        except Exception:
            content = escape(text)
    else:
        content = escape(text)

    return Panel(content, title=title, border_style="blue")


# ── Generated source code viewers ────────────────────────────────────


def _render_generated_files_index(files: list[dict[str, Any]]) -> Table:
    """Render a navigable index of generated source code files."""
    table = Table(title="Source Code Files", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Path", style="green")
    table.add_column("Language", style="cyan", width=12)
    table.add_column("Lines", justify="right", width=6)
    table.add_column("Preview", style="dim")

    for i, f in enumerate(files, 1):
        content = f.get("content", "")
        line_count = content.count("\n") + 1 if content else 0
        first_line = content.split("\n", 1)[0][:60] if content else ""
        table.add_row(
            str(i),
            escape(f.get("path", "?")),
            f.get("language", ""),
            str(line_count),
            escape(first_line),
        )

    return table


def render_source_file(file_data: dict[str, Any]) -> Panel:
    """Render a single source code file with syntax highlighting."""
    from rich.syntax import Syntax

    path = file_data.get("path", "unknown")
    content = file_data.get("content", "")
    lang = file_data.get("language", "")

    if not content.strip():
        return Panel("[dim]Empty file[/dim]", title=path, border_style="green")

    # Map common language names to Pygments lexer names.
    lexer_map = {
        "typescript": "typescript",
        "javascript": "javascript",
        "python": "python",
        "sql": "sql",
        "yaml": "yaml",
        "json": "json",
        "html": "html",
        "css": "css",
        "dockerfile": "dockerfile",
        "bash": "bash",
        "shell": "bash",
        "markdown": "markdown",
    }
    lexer = lexer_map.get(lang.lower(), lang.lower()) or "text"

    try:
        syntax = Syntax(
            content,
            lexer,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
    except Exception:
        syntax = Syntax(content, "text", line_numbers=True, word_wrap=True)

    return Panel(syntax, title=path, border_style="green")


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


# ── Phase 4: Inline progress display (Claude Code-style) ────────────

# Status words replace colored icons — near-monochrome palette.
_STATUS_WORDS: dict[str, tuple[str, str]] = {
    "completed": ("completed", "dim"),
    "running": ("running", ""),
    "failed": ("failed", "red"),
    "pending": ("pending", "dim"),
    "interrupted": ("interrupted", "dim"),
    "cancelled": ("cancelled", "dim"),
}

# Agent state words replace colored dots.
_AGENT_STATE_WORDS: dict[str, tuple[str, str]] = {
    "idle": ("", ""),  # not shown
    "thinking": ("thinking", ""),
    "tool_use": ("tool_use", ""),
    "reviewing": ("reviewing", ""),
    "handing_off": ("handing_off", ""),
    "done": ("", ""),  # not shown
    "error": ("error", "red"),
}


# ── Phase 7: Agent presence display ──────────────────────────────────


class ActivityMode(StrEnum):
    """Display verbosity for agent activity feed."""

    MINIMAL = "minimal"
    STATUS = "status"
    CONVERSATION = "conversation"
    VERBOSE = "verbose"


_PRESENCE_EVENT_STATE_MAP: dict[str, AgentState] = {
    "agent_thinking": AgentState.THINKING,
    "agent_tool_call": AgentState.TOOL_USE,
    "agent_reviewing": AgentState.REVIEWING,
    "agent_state_changed": AgentState.IDLE,
}


# ── Formatting helpers (Claude Code-style) ───────────────────────────


def _format_header(
    project_name: str,
    status: str | None = None,
) -> Text:
    """Format header line: ``colette v{version}  {project}  [status]``."""
    t = Text()
    t.append("colette", style="dim")
    t.append(f" v{__version__}", style="dim")
    t.append(f"  {project_name}")
    if status:
        style = "red" if "failed" in status else "dim"
        t.append(f"  {status}", style=style)
    return t


def _format_stage_line(
    stage: StageState,
    max_name_len: int,
    *,
    show_tokens: bool = False,
) -> Text:
    """Format a single stage line with column-aligned fields."""
    name = stage.name.ljust(max_name_len)
    word, style = _STATUS_WORDS.get(stage.status, (stage.status, "dim"))

    t = Text()
    t.append("  ")  # 2-space indent

    if stage.status == "running":
        t.append(name, style="bold")
        t.append(f"  {word}")
    elif stage.status == "failed":
        t.append(f"{name}  {word}", style="red")
    else:
        t.append(f"{name}  {word}", style=style)

    if stage.elapsed_seconds:
        elapsed = _format_elapsed(stage.elapsed_seconds)
        t.append(f"  {elapsed}", style="dim")

    if show_tokens and stage.tokens_used:
        t.append(f"  {stage.tokens_used:,} tokens", style="dim")

    return t


def _format_elapsed(seconds: float) -> str:
    """Format seconds as a human-readable duration (e.g. '2m 34s' or '12s')."""
    if seconds >= 60:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m}m {s}s"
    return f"{int(seconds)}s"


def _format_agent_line(
    agent: AgentPresence,
    width: int = 80,
) -> Text | None:
    """Format agent status line, or None if agent is idle/done."""
    word, style = _AGENT_STATE_WORDS.get(agent.state.value, ("", ""))
    if not word:
        return None

    t = Text()
    t.append("  ")  # 2-space indent
    name = agent.display_name or agent.agent_id
    t.append(name)
    t.append(f"  {word}", style=style)

    activity = agent.activity or ""
    if agent.state == AgentState.HANDING_OFF and agent.target_agent:
        activity = f"→ {agent.target_agent}: {activity}"
    if activity:
        # Truncate message to fit terminal width.
        max_msg = width - len(name) - len(word) - 10
        if max_msg > 0:
            if len(activity) > max_msg:
                activity = activity[: max_msg - 1] + "…"
            t.append(f'  "{activity}"', style="dim")

    return t


def _format_log_entry(
    entry: StreamLogEntry,
    max_agent_len: int,
) -> Text:
    """Format a single stream log entry."""
    t = Text()
    t.append("  ")  # 2-space indent
    t.append(_format_time(entry.timestamp), style="dim")
    t.append("  ")

    agent = entry.agent.ljust(max_agent_len)
    t.append(agent)
    t.append("  ")

    label = entry.event_type.replace("agent_", "").replace("stage_", "").replace("_", " ")
    if entry.message:
        msg = entry.message[:200]
        t.append(f'"{msg}"', style="dim")
    else:
        t.append(label, style="dim")

    return t


def _format_live_output(
    buffers: dict[str, str],
    width: int = 80,
    max_lines: int = 12,
) -> Text:
    """Format live token output with ``> `` prefix."""
    t = Text()
    if not buffers:
        return t

    for _agent, text in buffers.items():
        lines = text.split("\n")
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        for line in tail:
            # Wrap at terminal width.
            if len(line) > width - 6:
                line = line[: width - 6]
            t.append("  > ", style="dim")
            t.append(line)
            t.append("\n")

    # Remove trailing newline.
    if t.plain.endswith("\n"):
        t.right_crop(1)

    return t


# ── Rendering functions (Claude Code-style) ──────────────────────────


def build_agent_activity_panel(agents: tuple[AgentPresence, ...]) -> Text:
    """Build agent status lines (plain text, no panel)."""
    width = shutil.get_terminal_size((80, 24)).columns
    t = Text()
    for agent in agents:
        line = _format_agent_line(agent, width=width)
        if line is not None:
            if t.plain:
                t.append("\n")
            t.append_text(line)
    return t


def build_conversation_feed(
    entries: tuple[ConversationEntry, ...],
    max_lines: int = 10,
) -> Text:
    """Build a scrolling conversation feed (plain text)."""
    t = Text()
    visible = entries[-max_lines:] if len(entries) > max_lines else entries
    for i, entry in enumerate(visible):
        if i > 0:
            t.append("\n")
        ts = _format_time(entry.timestamp)
        name = entry.display_name or entry.agent_id
        if entry.target_agent:
            name += f" → {entry.target_agent}"
        t.append("  ", style="dim")
        t.append(ts, style="dim")
        t.append(f"  {name}  ")
        t.append(f'"{entry.message}"', style="dim")
    return t


@dataclass(frozen=True)
class StreamLogEntry:
    """A single log line for the verbose streaming panel."""

    timestamp: datetime
    agent: str
    event_type: str
    message: str
    tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0


_MAX_STREAM_LOG = 15
_MAX_STREAM_BUFFER = 2000  # max chars kept per agent in the live buffer


def build_live_output_panel(
    buffers: dict[str, str],
    max_lines: int = 12,
) -> Text:
    """Build live LLM output with ``> `` prefix (no panel)."""
    width = shutil.get_terminal_size((80, 24)).columns
    return _format_live_output(buffers, width=width, max_lines=max_lines)


def build_streaming_log(
    entries: tuple[StreamLogEntry, ...],
    max_lines: int = 15,
) -> Text:
    """Build a plain-text streaming log."""
    t = Text()
    visible = entries[-max_lines:] if len(entries) > max_lines else entries
    if not visible:
        return t

    max_agent_len = max((len(e.agent) for e in visible), default=10)
    for i, entry in enumerate(visible):
        if i > 0:
            t.append("\n")
        t.append_text(_format_log_entry(entry, max_agent_len))

    return t


def _format_time(dt: datetime) -> str:
    """Format a datetime as HH:MM:SS for the conversation feed."""
    return dt.strftime("%H:%M:%S")


def build_progress_renderable(
    stages: tuple[StageState, ...],
    error_message: str = "",
) -> Text:
    """Build a plain-text stage list (Claude Code-style)."""
    max_name_len = max(len(s.name) for s in stages) if stages else 14
    t = Text()
    for i, stage in enumerate(stages):
        if i > 0:
            t.append("\n")
        t.append_text(_format_stage_line(stage, max_name_len))

    if error_message:
        t.append("\n\n")
        t.append(f"  error: {error_message}", style="red")

    return t


def build_summary_panel(
    stages: tuple[StageState, ...],
    project_id: str,
    final_status: str,
    error_message: str = "",
) -> Text:
    """Build a plain-text completion summary (Claude Code-style)."""
    total_elapsed = sum(s.elapsed_seconds for s in stages)
    total_tokens = sum(s.tokens_used for s in stages)
    completed_count = sum(1 for s in stages if s.status == "completed")

    # Header with final status.
    if final_status == "completed":
        status_suffix = f"completed in {_format_elapsed(total_elapsed)}"
    elif final_status == "failed":
        failed_stage = next((s.name for s in stages if s.status == "failed"), "unknown")
        status_suffix = f"failed at {failed_stage}"
    else:
        status_suffix = final_status

    t = _format_header(project_id, status=status_suffix)
    t.append("\n")

    # Stage lines with token counts.
    max_name_len = max(len(s.name) for s in stages) if stages else 14
    for stage in stages:
        t.append("\n")
        t.append_text(_format_stage_line(stage, max_name_len, show_tokens=True))

    # Totals.
    t.append("\n\n")
    t.append(f"  {completed_count}/{len(stages)} completed", style="dim")
    t.append(f"  total tokens  {total_tokens:,}", style="dim")

    if error_message:
        t.append("\n\n")
        t.append(f"  error: {error_message}", style="red")

    return t


class PipelineProgressDisplay:
    """Live pipeline progress state machine (Phase 4).

    Accepts SSE event dicts via :meth:`process_event`, tracks stage
    states immutably, and produces Rich renderables via :meth:`render`.
    """

    def __init__(
        self,
        project_id: str,
        target_console: Console | None = None,
        activity_mode: ActivityMode = ActivityMode.STATUS,
    ) -> None:
        self._project_id = project_id
        self._stages = tuple(StageState(name=n) for n in PIPELINE_STAGES)
        self._error = ""
        self._final_status = ""
        self._activity_mode = activity_mode
        self._presence = AgentPresenceTracker()
        self._project_id_for_presence = project_id
        self._pending_approval: dict[str, Any] | None = None
        self._stream_log: tuple[StreamLogEntry, ...] = ()
        # Per-agent rolling text buffer for live token streaming.
        self._stream_buffers: dict[str, str] = {}

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

    @property
    def pending_approval(self) -> dict[str, Any] | None:
        """Non-None when the pipeline is paused waiting for human approval."""
        return self._pending_approval

    def clear_approval(self) -> None:
        """Clear pending approval after the user has responded."""
        self._pending_approval = None

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

    def _append_log(self, event: dict[str, Any]) -> None:
        """Append a stream log entry from an event dict."""
        detail = event.get("detail", {})
        entry = StreamLogEntry(
            timestamp=datetime.now(tz=UTC),
            agent=event.get("agent", ""),
            event_type=event.get("event_type", ""),
            message=event.get("message", ""),
            tokens=event.get("tokens_used", 0) or detail.get("tokens", 0),
            cache_read=detail.get("cache_read_tokens", 0),
            cache_write=detail.get("cache_creation_tokens", 0),
        )
        log = (*self._stream_log, entry)
        if len(log) > _MAX_STREAM_LOG:
            log = log[len(log) - _MAX_STREAM_LOG :]
        self._stream_log = log

    def _auto_advance_stages(self, target_idx: int) -> None:
        """Mark all prior stages as completed and target as running.

        Handles the race condition where the CLI reconnects after an
        approval gate and misses STAGE_STARTED / STAGE_COMPLETED events.
        """
        for i in range(target_idx):
            if self._stages[i].status in ("pending", "running"):
                self._replace_stage(i, status="completed", agent="", message="")
        if self._stages[target_idx].status == "pending":
            self._replace_stage(target_idx, status="running", agent="", message="")

    def process_event(self, event: dict[str, Any]) -> bool:
        """Process an SSE event dict. Returns True on terminal event."""
        etype = event.get("event_type", "")
        stage = event.get("stage", "")
        idx = self._stage_index(stage) if stage else None

        if etype == "stage_started" and idx is not None:
            self._auto_advance_stages(idx)

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
            self._auto_advance_stages(idx)
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

        elif etype == "approval_required":
            self._pending_approval = event.get("detail", event)
            self._pending_approval["stage"] = stage  # ensure stage is set
            return True  # break Live loop for interactive prompt

        elif etype in ("pipeline_completed", "complete"):
            # If a gate already failed, this is not a true success.
            self._final_status = "failed" if self._error else "completed"
            return True

        elif etype == "pipeline_failed":
            self._final_status = "failed"
            self._error = event.get("message", "Pipeline failed")
            return True

        # Phase 7: agent presence events
        elif etype in _PRESENCE_EVENT_STATE_MAP:
            self._handle_presence_event(event, etype)

        elif etype == "agent_handoff":
            self._handle_handoff_event(event)

        elif etype == "agent_message":
            self._handle_message_event(event)
            # Clear the stream buffer for this agent (final response arrived).
            agent = event.get("agent", "")
            if agent:
                self._stream_buffers.pop(agent, None)

        elif etype == "agent_stream_chunk":
            self._handle_stream_chunk(event)

        # Append to streaming log for verbose/conversation modes.
        # Skip individual stream chunks — they're shown in the live buffer.
        if etype != "agent_stream_chunk" and (
            etype.startswith("agent_") or etype.startswith("stage_")
        ):
            self._append_log(event)

        return False

    def _handle_presence_event(self, event: dict[str, Any], etype: str) -> None:
        """Update agent presence for thinking/tool_call/reviewing/state_changed."""
        state = _PRESENCE_EVENT_STATE_MAP.get(etype, AgentState.IDLE)
        agent_state = event.get("agent_state", "")
        if agent_state:
            state = AgentState(agent_state)
        self._presence.update_agent(
            self._project_id_for_presence,
            event.get("agent", "unknown"),
            display_name=event.get("agent", ""),
            stage=event.get("stage", ""),
            state=state,
            activity=event.get("message", ""),
            model=event.get("model", ""),
        )

    def _handle_handoff_event(self, event: dict[str, Any]) -> None:
        """Update agent presence for a handoff and add conversation entry."""
        target = event.get("target_agent", "") or event.get("detail", {}).get("target_agent", "")
        self._presence.update_agent(
            self._project_id_for_presence,
            event.get("agent", "unknown"),
            display_name=event.get("agent", ""),
            stage=event.get("stage", ""),
            state=AgentState.HANDING_OFF,
            activity=event.get("message", ""),
            model=event.get("model", ""),
            target_agent=target,
        )
        self._presence.add_conversation(
            self._project_id_for_presence,
            ConversationEntry(
                agent_id=event.get("agent", "unknown"),
                display_name=event.get("agent", ""),
                stage=event.get("stage", ""),
                message=event.get("message", ""),
                target_agent=target,
            ),
        )

    def _handle_stream_chunk(self, event: dict[str, Any]) -> None:
        """Append a token chunk to the per-agent live buffer."""
        agent = event.get("agent", "unknown")
        chunk = event.get("message", "")
        buf = self._stream_buffers.get(agent, "")
        buf += chunk
        # Keep only the tail to prevent unbounded growth.
        if len(buf) > _MAX_STREAM_BUFFER:
            buf = buf[-_MAX_STREAM_BUFFER:]
        self._stream_buffers[agent] = buf

    def _handle_message_event(self, event: dict[str, Any]) -> None:
        """Append a conversation entry for an agent message."""
        target = event.get("target_agent", "") or event.get("detail", {}).get("target_agent", "")
        self._presence.add_conversation(
            self._project_id_for_presence,
            ConversationEntry(
                agent_id=event.get("agent", "unknown"),
                display_name=event.get("agent", ""),
                stage=event.get("stage", ""),
                message=event.get("message", ""),
                target_agent=target,
            ),
        )

    # ── Read-only access to presence (for testing) ─────────────────────

    @property
    def agents(self) -> tuple[AgentPresence, ...]:
        return self._presence.get_agents(self._project_id_for_presence)

    @property
    def conversation(self) -> tuple[ConversationEntry, ...]:
        return self._presence.get_conversation(self._project_id_for_presence)

    # ── Rendering ─────────────────────────────────────────────────────

    @property
    def stream_log(self) -> tuple[StreamLogEntry, ...]:
        """Return the stream log entries."""
        return self._stream_log

    @property
    def stream_buffers(self) -> dict[str, str]:
        """Return per-agent live token buffers (read-only snapshot)."""
        return dict(self._stream_buffers)

    def render(self) -> Text | Group:
        """Return the current renderable based on activity mode."""
        if self.is_done:
            return build_summary_panel(
                self._stages, self._project_id, self._final_status, self._error
            )

        # Header + stage list.
        header = _format_header(self._project_id)
        progress = build_progress_renderable(self._stages, self._error)

        sections: list[Text] = [header, Text(""), progress]

        if self._activity_mode == ActivityMode.MINIMAL:
            return _join_texts(sections)

        # STATUS+: add agent line.
        agents = self._presence.get_agents(self._project_id_for_presence)
        agent_text = build_agent_activity_panel(agents)
        if agent_text.plain.strip():
            sections.append(Text(""))
            sections.append(agent_text)

        if self._activity_mode == ActivityMode.STATUS:
            return _join_texts(sections)

        # CONVERSATION+: add stream log.
        stream = build_streaming_log(self._stream_log)
        if stream.plain.strip():
            sections.append(Text(""))
            sections.append(stream)

        if self._activity_mode == ActivityMode.CONVERSATION:
            return _join_texts(sections)

        # VERBOSE: add live output + conversation feed.
        live_out = build_live_output_panel(self._stream_buffers)
        if live_out.plain.strip():
            sections.append(Text(""))
            sections.append(live_out)

        entries = self._presence.get_conversation(self._project_id_for_presence)
        feed = build_conversation_feed(entries)
        if feed.plain.strip():
            sections.append(Text(""))
            sections.append(feed)

        return _join_texts(sections)


def _join_texts(sections: list[Text]) -> Text:
    """Join multiple Text objects with newlines into a single Text."""
    result = Text()
    for i, section in enumerate(sections):
        if i > 0:
            result.append("\n")
        result.append_text(section)
    return result
