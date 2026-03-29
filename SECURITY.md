# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in Colette, **do not open a public issue**. Instead:

1. Email the maintainers at **security@colette-project.dev** (or use GitHub's private vulnerability reporting if enabled on this repository)
2. Include a description of the vulnerability, steps to reproduce, and potential impact
3. Allow reasonable time for a fix before public disclosure

We aim to acknowledge reports within 48 hours and provide an initial assessment within 5 business days.

## Security Design Principles

Colette handles LLM API keys, database credentials, and potentially sensitive project data. The following principles guide the project's security posture:

### Credential Management

- **No hardcoded secrets.** All credentials are loaded from environment variables or a secrets manager.
- API keys, database passwords, and tokens must never appear in source code, logs, or handoff schemas.
- The `.env.example` file documents required variables without containing real values.

### Input Sanitization

- All MCP tool inputs are sanitized for prompt injection before reaching LLM context (`src/colette/tools/base.py`).
- File paths are validated to prevent path traversal attacks.
- Shell commands executed by tool wrappers run in sandboxed subprocesses with argument validation.

### Audit Logging

- Every tool invocation is logged with agent ID, tool name, sanitized parameters, and outcome.
- Secret values are redacted from all log output.

### Human Oversight

- Production deployments, database migrations, and security architecture changes require human approval (Tier 0).
- API contract changes, new dependencies, and infrastructure modifications require human review (Tier 1).
- Confidence-gated operations escalate to humans when confidence falls below the configured threshold (Tier 2).

### Dependency Management

- Dependencies are pinned to version ranges and audited with `pip-audit`.
- Static analysis with `bandit` runs as part of CI and the `make security` target.

## Security Checks for Contributors

Before submitting code, verify:

- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user/external inputs are validated
- [ ] File system operations use sanitized paths
- [ ] Subprocess calls use parameterized arguments (no shell injection)
- [ ] Error messages do not leak internal details or credentials
- [ ] New dependencies have been audited (`make security`)
