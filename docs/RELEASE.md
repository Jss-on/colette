# Release Process

Colette uses [Semantic Versioning](https://semver.org/) with automated changelog generation via [git-cliff](https://git-cliff.org/).

## Prerequisites

- **git-cliff** installed: `cargo install git-cliff` or `pipx install git-cliff` or [download binary](https://github.com/orhun/git-cliff/releases)
- On `main` branch with a clean working tree
- All CI checks passing (`make check`)

## How to Release

### 1. Choose the version bump

| Commit types since last release | Bump     | Command           |
|---------------------------------|----------|-------------------|
| Only `fix:`, `docs:`, `perf:`  | Patch    | `make bump-patch` |
| Any `feat:`                     | Minor    | `make bump-minor` |
| Breaking changes (`feat!:`)     | Major    | `make bump-major` |

### 2. Bump, tag, and generate changelog

```bash
# Runs all quality checks first, then:
# - Generates CHANGELOG.md from commit history
# - Creates a release commit
# - Tags the commit with the new version
make bump-patch   # or bump-minor / bump-major
```

### 3. Review the changelog

```bash
git diff HEAD~1 CHANGELOG.md
```

If the changelog looks wrong, reset and redo:

```bash
git reset --soft HEAD~1
git tag -d v<new-version>
# Fix issues, then re-run make bump-*
```

### 4. Push the tag to trigger the release

```bash
make release
```

This pushes the tag to GitHub, which triggers the [release workflow](../.github/workflows/release.yml):

1. **Build & Verify** — lint, typecheck, test, build wheel, verify version matches tag
2. **GitHub Release** — creates a release with auto-generated notes and `.whl`/`.tar.gz` artifacts
3. **Docker Image** — builds and pushes to `ghcr.io/jss-on/colette` with semver tags

### 5. Push the main branch

```bash
git push origin main
```

## What Gets Published

| Artifact | Location | Tags |
|----------|----------|------|
| GitHub Release | [Releases page](https://github.com/Jss-on/colette/releases) | `vX.Y.Z` |
| Docker image | `ghcr.io/jss-on/colette` | `X.Y.Z`, `X.Y`, `latest` |
| Python wheel | GitHub Release assets | `colette-X.Y.Z-py3-none-any.whl` |

## Hotfix Process

For urgent fixes to a released version:

```bash
# Branch from the release tag
git checkout -b fix/critical-bug v0.2.0

# Make the fix, commit, push
git commit -m "fix: critical bug description"
git push -u origin fix/critical-bug

# Open a PR to main, merge, then bump patch
git checkout main
git pull
make bump-patch
make release
git push origin main
```

## Version Resolution

Version is **single-sourced from git tags** via `hatch-vcs`:

- **Tagged commits** (releases): `0.2.0`
- **Post-tag commits** (development): `0.2.1.dev5+g1a2b3c4`
- **No tags** (fallback): `0.0.0-dev`

There is no hardcoded version in `pyproject.toml` or `__init__.py`.
