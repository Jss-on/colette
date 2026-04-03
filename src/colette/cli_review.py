"""Textual TUI app for interactive approval review (FR-HIL-003)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _get(d: dict[str, Any] | Any, key: str, default: Any = "") -> Any:
    if isinstance(d, dict):
        return d.get(key, default)
    return default


_LEXER_MAP: dict[str, str] = {
    "typescript": "typescript", "javascript": "javascript",
    "python": "python", "sql": "sql", "yaml": "yaml",
    "json": "json", "html": "html", "css": "css",
    "dockerfile": "dockerfile", "bash": "bash",
    "shell": "bash", "markdown": "markdown",
}


# ── Main TUI app ────────────────────────────────────────────────────


class ApprovalReviewApp(App[str]):
    """Interactive TUI for reviewing a stage's output before approval.

    Returns ``"approved"`` or ``"rejected"`` via :meth:`exit`.
    """

    CSS = """
    Screen {
        layout: vertical;
    }
    #summary-bar {
        height: auto;
        background: $surface;
        padding: 0 2;
        color: $text;
    }
    #summary-bar .label {
        margin: 0 1;
    }
    TabbedContent {
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    RichLog {
        height: 1fr;
    }
    VerticalScroll {
        height: 1fr;
    }
    #button-bar {
        height: auto;
        align: center middle;
        padding: 1 0;
        background: $surface;
    }
    #button-bar Button {
        margin: 0 2;
        min-width: 16;
    }
    .file-viewer {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "approve", "Approve", show=True),
        Binding("r", "reject", "Reject", show=True),
        Binding("q", "quit_app", "Quit / Reject", show=True),
    ]

    def __init__(
        self,
        approval_data: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        self._approval = approval_data
        self._summary: dict[str, Any] = approval_data.get("handoff_summary", {})
        self._stage = approval_data.get("stage", self._summary.get("stage", "?"))
        super().__init__(**kwargs)

    # ── Compose ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        stage_label = self._stage.title()
        tier = self._approval.get("tier", "?")
        score = self._approval.get("confidence_score")
        score_str = f"  Score: {score:.2f}" if score is not None else ""

        yield Header()
        yield Label(
            f"  Stage: [bold]{stage_label}[/bold]   "
            f"Tier: [bold yellow]{tier}[/bold yellow]{score_str}",
            id="summary-bar",
        )

        with TabbedContent():
            yield from self._build_tabs()

        with Horizontal(id="button-bar"):
            yield Button("Approve", id="approve", variant="success")
            yield Button("Reject", id="reject", variant="error")

        yield Footer()

    # ── Tab builders ─────────────────────────────────────────────────

    def _build_tabs(self) -> list[TabPane]:
        panes: list[TabPane] = []
        s = self._summary
        stage = self._stage

        if stage == "requirements":
            stories = s.get("user_stories", [])
            if stories:
                panes.append(self._table_pane(
                    "User Stories", "stories",
                    ["ID", "Title", "Priority", "Acceptance Criteria"],
                    [
                        (
                            _get(st, "id", "?"),
                            _get(st, "title", "?"),
                            _get(st, "priority", "?"),
                            "\n".join(_get(st, "acceptance_criteria", [])[:5]),
                        )
                        for st in stories
                    ],
                ))
            nfrs = s.get("nfrs", [])
            if nfrs:
                panes.append(self._table_pane(
                    "NFRs", "nfrs",
                    ["ID", "Category", "Description", "Target"],
                    [
                        (
                            _get(n, "id"), _get(n, "category"),
                            _get(n, "description"), _get(n, "target", "-"),
                        )
                        for n in nfrs
                    ],
                ))
            constraints = s.get("tech_constraints", [])
            if constraints:
                panes.append(self._table_pane(
                    "Constraints", "constraints",
                    ["ID", "Description", "Rationale"],
                    [
                        (_get(c, "id"), _get(c, "description"), _get(c, "rationale"))
                        for c in constraints
                    ],
                ))

        elif stage == "design":
            endpoints = s.get("endpoints", [])
            if endpoints:
                panes.append(self._table_pane(
                    f"Endpoints ({len(endpoints)})", "endpoints",
                    ["#", "Method", "Path", "Summary", "Auth"],
                    [
                        (
                            str(i), _get(ep, "method"), _get(ep, "path"),
                            _get(ep, "summary"),
                            "Y" if _get(ep, "auth_required", True) else "N",
                        )
                        for i, ep in enumerate(endpoints, 1)
                    ],
                ))
            entities = s.get("db_entities", [])
            if entities:
                panes.append(self._table_pane(
                    f"DB Entities ({len(entities)})", "entities",
                    ["Entity", "Fields", "Indexes", "Relationships"],
                    [
                        (
                            _get(e, "name"),
                            ", ".join(
                                f"{_get(f, 'name')}: {_get(f, 'type')}"
                                for f in _get(e, "fields", [])[:8]
                            ),
                            ", ".join(_get(e, "indexes", [])) or "-",
                            ", ".join(_get(e, "relationships", [])) or "-",
                        )
                        for e in entities
                    ],
                ))
            components = s.get("ui_components", [])
            if components:
                panes.append(self._table_pane(
                    f"UI Components ({len(components)})", "components",
                    ["Name", "Description", "Route", "Children"],
                    [
                        (
                            _get(c, "name"), _get(c, "description"),
                            _get(c, "route", "-") or "-",
                            ", ".join(_get(c, "children", [])) or "-",
                        )
                        for c in components
                    ],
                ))
            tech = s.get("tech_stack", {})
            if tech:
                panes.append(self._table_pane(
                    "Tech Stack", "tech",
                    ["Role", "Technology"],
                    [(role, str(val)) for role, val in tech.items()],
                ))
            adrs = s.get("adrs", [])
            if adrs:
                panes.append(self._richlog_pane("ADRs", "adrs", self._format_adrs(adrs)))
            spec = s.get("openapi_spec", "")
            if spec:
                panes.append(self._syntax_pane("OpenAPI Spec", "openapi", spec, "json"))
            arch = s.get("architecture_summary", "")
            if arch:
                panes.append(self._text_pane("Architecture", "arch", arch))
            sec = s.get("security_design", "")
            if sec:
                panes.append(self._text_pane("Security", "security", sec))

        elif stage == "implementation":
            gen_files = s.get("generated_files", [])
            if gen_files:
                panes.append(self._files_pane("Source Files", "src-files", gen_files))
            files = s.get("files", [])
            if files:
                panes.append(self._table_pane(
                    "Change Summary", "changes",
                    ["Path", "Language", "Lines+"],
                    [(
                        _get(f, "path", "?"),
                        _get(f, "language", ""),
                        str(_get(f, "lines_added", 0)),
                    ) for f in files],
                ))

        elif stage == "testing":
            gen_files = s.get("generated_files", [])
            if gen_files:
                panes.append(self._files_pane("Test Files", "test-files", gen_files))
            findings = s.get("security_findings", [])
            if findings:
                panes.append(self._table_pane(
                    "Security Findings", "findings",
                    ["Severity", "Category", "Description"],
                    [
                        (_get(f, "severity"), _get(f, "category"), _get(f, "description"))
                        for f in findings
                    ],
                ))

        elif stage in ("staging", "deployment"):
            gen_files = s.get("generated_files", [])
            if gen_files:
                panes.append(self._files_pane("Deploy Files", "deploy-files", gen_files))

        if not panes:
            panes.append(TabPane("Info", Static("No detailed data available for this stage.")))

        return panes

    # ── Pane factory methods ─────────────────────────────────────────

    @staticmethod
    def _table_pane(
        title: str,
        pane_id: str,
        columns: list[str],
        rows: list[tuple[str, ...]],
    ) -> TabPane:
        table = DataTable(id=f"dt-{pane_id}", zebra_stripes=True)
        pane = TabPane(title, table, id=pane_id)
        # Columns and rows are added in on_mount via _populate_tables.
        table._meta = {"columns": columns, "rows": rows}  # type: ignore[attr-defined]
        return pane

    @staticmethod
    def _richlog_pane(title: str, pane_id: str, content: str) -> TabPane:
        log = RichLog(id=f"rl-{pane_id}", markup=True, wrap=True)
        log._deferred_content = content  # type: ignore[attr-defined]
        return TabPane(title, log, id=pane_id)

    @staticmethod
    def _syntax_pane(title: str, pane_id: str, code: str, lang: str) -> TabPane:
        log = RichLog(id=f"rl-{pane_id}", wrap=False)
        log._deferred_syntax = (code, lang)  # type: ignore[attr-defined]
        return TabPane(title, log, id=pane_id)

    @staticmethod
    def _text_pane(title: str, pane_id: str, text: str) -> TabPane:
        scroll = VerticalScroll(Static(text, markup=False), id=f"vs-{pane_id}")
        return TabPane(title, scroll, id=pane_id)

    def _files_pane(self, title: str, pane_id: str, files: list[dict[str, Any]]) -> TabPane:
        """Create a tab pane with a file index table.

        When the user selects a row, the file content is shown below.
        """
        table = DataTable(id=f"dt-{pane_id}", zebra_stripes=True)
        viewer = RichLog(id=f"fv-{pane_id}", wrap=False)
        table._meta = {  # type: ignore[attr-defined]
            "columns": ["#", "Path", "Language", "Lines"],
            "rows": [
                (
                    str(i),
                    _get(f, "path", "?"),
                    _get(f, "language", ""),
                    str(f.get("content", "").count("\n") + 1 if f.get("content") else 0),
                )
                for i, f in enumerate(files, 1)
            ],
            "files": files,
            "viewer_id": f"fv-{pane_id}",
        }
        return TabPane(title, table, viewer, id=pane_id)

    # ── Lifecycle ────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = "Colette — Approval Review"
        self.sub_title = f"{self._stage.title()} Gate"
        self._populate_tables()
        self._populate_richlogs()

    def _populate_tables(self) -> None:
        for dt in self.query(DataTable):
            meta = getattr(dt, "_meta", None)
            if not meta:
                continue
            dt.add_columns(*meta["columns"])
            for row in meta["rows"]:
                dt.add_row(*row)
            dt.cursor_type = "row"

    def _populate_richlogs(self) -> None:
        for rl in self.query(RichLog):
            content = getattr(rl, "_deferred_content", None)
            if content:
                rl.write(content)
            syntax_data = getattr(rl, "_deferred_syntax", None)
            if syntax_data:
                code, lang = syntax_data
                try:
                    rl.write(Syntax(
                        code, lang, theme="monokai",
                        line_numbers=True, word_wrap=True,
                    ))
                except Exception:
                    rl.write(code)

    # ── Event handlers ───────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show file content when a row is selected in a files table."""
        dt = event.data_table
        meta = getattr(dt, "_meta", None)
        if not meta or "files" not in meta:
            return

        viewer_id = meta.get("viewer_id", "")
        try:
            viewer = self.query_one(f"#{viewer_id}", RichLog)
        except Exception:
            return

        row = dt.get_row(event.row_key)
        idx = int(row[0]) - 1
        files = meta["files"]
        if 0 <= idx < len(files):
            f = files[idx]
            content = _get(f, "content", "")
            lang = _get(f, "language", "text")
            path = _get(f, "path", "unknown")
            lexer = _LEXER_MAP.get(lang.lower(), lang.lower()) or "text"

            viewer.clear()
            viewer.write(Text(f"── {path} ──", style="bold green"))
            if content:
                try:
                    viewer.write(Syntax(
                        content, lexer, theme="monokai",
                        line_numbers=True, word_wrap=True,
                    ))
                except Exception:
                    viewer.write(content)
            else:
                viewer.write("[dim]Empty file[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.exit("approved")
        elif event.button.id == "reject":
            self.exit("rejected")

    def action_approve(self) -> None:
        self.exit("approved")

    def action_reject(self) -> None:
        self.exit("rejected")

    def action_quit_app(self) -> None:
        self.exit("rejected")

    # ── Formatting helpers ───────────────────────────────────────────

    @staticmethod
    def _format_adrs(adrs: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for adr in adrs:
            lines.append(f"[bold cyan]{_get(adr, 'id')}: {_get(adr, 'title')}[/bold cyan]")
            lines.append(f"  Status: {_get(adr, 'status')}")
            ctx = _get(adr, "context")
            if ctx:
                lines.append(f"  Context: {ctx[:300]}")
            dec = _get(adr, "decision")
            if dec:
                lines.append(f"  Decision: {dec[:300]}")
            alts = _get(adr, "alternatives", [])
            if alts:
                lines.append("  Alternatives:")
                for alt in alts:
                    lines.append(f"    - {alt}")
            lines.append("")
        return "\n".join(lines)
