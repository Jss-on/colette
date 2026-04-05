"""Tests for the GitHub integration service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from colette.config import Settings
from colette.services.github import GitHubError, GitHubService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_with_token() -> Settings:
    return Settings(
        github_token="ghp_test123",
        github_owner="test-org",
        github_repo_prefix="colette",
        github_repo_visibility="private",
    )


@pytest.fixture
def settings_no_token() -> Settings:
    return Settings(github_token="")


@pytest.fixture
def service(settings_with_token: Settings) -> GitHubService:
    return GitHubService(settings_with_token)


@pytest.fixture
def service_no_token(settings_no_token: Settings) -> GitHubService:
    return GitHubService(settings_no_token)


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_is_configured_true(service: GitHubService) -> None:
    assert service.is_configured is True


@pytest.mark.unit
def test_is_configured_false(service_no_token: GitHubService) -> None:
    assert service_no_token.is_configured is False


# ---------------------------------------------------------------------------
# generate_repo_name
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_repo_name_basic(service: GitHubService) -> None:
    name = service.generate_repo_name("My Todo App", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert name == "colette-my-todo-app-a1b2c3d4"


@pytest.mark.unit
def test_generate_repo_name_special_chars(service: GitHubService) -> None:
    name = service.generate_repo_name("Hello! World@#$%", "abcdef1234567890abcdef1234567890")
    assert name == "colette-hello-world-abcdef12"
    assert all(c.isalnum() or c == "-" for c in name)


@pytest.mark.unit
def test_generate_repo_name_truncation(service: GitHubService) -> None:
    long_name = "a" * 100
    name = service.generate_repo_name(long_name, "12345678abcdef")
    # prefix + "-" + 40 chars + "-" + 8 chars = "colette-" + slug + "-" + id
    slug_part = name.removeprefix("colette-").rsplit("-", 1)[0]
    assert len(slug_part) <= 40


@pytest.mark.unit
def test_generate_repo_name_empty_name(service: GitHubService) -> None:
    name = service.generate_repo_name("", "abcdef1234567890")
    assert name == "colette-abcdef12"


@pytest.mark.unit
def test_generate_repo_name_hyphens_only(service: GitHubService) -> None:
    name = service.generate_repo_name("---", "abcdef1234567890")
    assert name == "colette-abcdef12"


# ---------------------------------------------------------------------------
# create_repository
# ---------------------------------------------------------------------------


@pytest.mark.unit
@respx.mock
async def test_create_repository_org(service: GitHubService) -> None:
    respx.post("https://api.github.com/orgs/test-org/repos").mock(
        return_value=httpx.Response(
            201,
            json={"html_url": "https://github.com/test-org/colette-app-12345678"},
        )
    )
    url = await service.create_repository("colette-app-12345678", "A test project")
    assert url == "https://github.com/test-org/colette-app-12345678"


@pytest.mark.unit
@respx.mock
async def test_create_repository_user() -> None:
    svc = GitHubService(Settings(github_token="ghp_test", github_owner=""))
    respx.post("https://api.github.com/user/repos").mock(
        return_value=httpx.Response(
            201,
            json={"html_url": "https://github.com/myuser/colette-app-12345678"},
        )
    )
    url = await svc.create_repository("colette-app-12345678", "A test project")
    assert url == "https://github.com/myuser/colette-app-12345678"


@pytest.mark.unit
@respx.mock
async def test_create_repository_error(service: GitHubService) -> None:
    respx.post("https://api.github.com/orgs/test-org/repos").mock(
        return_value=httpx.Response(422, json={"message": "Validation Failed"})
    )
    with pytest.raises(GitHubError, match="422"):
        await service.create_repository("colette-app", "desc")


# ---------------------------------------------------------------------------
# push_files (subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_push_files_sync_commands(service: GitHubService) -> None:
    """Verify git commands are called in the correct order."""
    commands_run: list[list[str]] = []

    def mock_run(cmd: list[str], **_kwargs: object) -> MagicMock:
        commands_run.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stdout = "abc123\n" if "rev-parse" in cmd else ""
        result.stderr = ""
        return result

    files = [
        {"path": "src/main.py", "content": "print('hello')"},
        {"path": "README.md", "content": "# Project"},
    ]

    with patch("colette.services.github.subprocess.run", side_effect=mock_run):
        sha = service._push_files_sync(
            "https://x-access-token:tok@github.com/org/repo.git",
            files,
            "Initial commit",
        )

    assert sha == "abc123"

    git_actions = [cmd[1] for cmd in commands_run]
    assert git_actions == [
        "init",
        "config",
        "config",
        "add",
        "commit",
        "remote",
        "push",
        "rev-parse",
    ]


# ---------------------------------------------------------------------------
# create_and_push (full flow)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_create_and_push_full_flow(service: GitHubService) -> None:
    with (
        patch.object(
            service,
            "create_repository",
            return_value="https://github.com/test-org/colette-app-a1b2c3d4",
        ),
        patch.object(service, "push_files", return_value="deadbeef"),
    ):
        url, name = await service.create_and_push(
            project_name="My App",
            project_id="a1b2c3d4-0000-0000-0000-000000000000",
            description="Test project",
            files=[{"path": "main.py", "content": "pass"}],
        )

    assert url == "https://github.com/test-org/colette-app-a1b2c3d4"
    assert name.startswith("colette-")
    assert "a1b2c3d4" in name


# ---------------------------------------------------------------------------
# collect_generated_files (enhanced)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_collect_generated_files_both_sources() -> None:
    from colette.artifacts import collect_generated_files

    state = {
        "metadata": {
            "generated_files": {
                "implementation": [
                    {"path": "src/main.py", "content": "# main"},
                    {"path": "src/utils.py", "content": "# utils"},
                ],
            },
        },
        "handoffs": {
            "implementation": {
                "generated_files": [
                    {"path": "src/main.py", "content": "# main (dup)"},
                    {"path": "src/models.py", "content": "# models"},
                ],
            },
        },
    }
    files = collect_generated_files(state)

    paths = [f["path"] for f in files]
    assert len(paths) == 3
    assert "src/main.py" in paths
    assert "src/utils.py" in paths
    assert "src/models.py" in paths
    # Metadata wins for dupes — content should be from metadata source.
    main_file = next(f for f in files if f["path"] == "src/main.py")
    assert main_file["content"] == "# main"


@pytest.mark.unit
def test_collect_generated_files_empty_state() -> None:
    from colette.artifacts import collect_generated_files

    assert collect_generated_files({}) == []
    assert collect_generated_files({"handoffs": {}, "metadata": {}}) == []
