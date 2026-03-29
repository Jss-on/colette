# Colette

**Multi-agent AI system for autonomous end-to-end software development.**

Colette orchestrates 16 specialized AI agents across a six-stage SDLC pipeline -- from natural language requirements through production deployment and monitoring.

```
User Request -> Requirements -> Design -> Implementation -> Testing -> Deployment -> Monitoring
```

## Key Features

- **Full SDLC coverage** -- requirements analysis, system design, code generation, testing, deployment, and monitoring
- **Typed handoffs** -- all inter-stage communication uses versioned Pydantic schemas
- **LLM-agnostic** -- Claude, GPT, and Gemini via LiteLLM gateway with automatic fallback chains
- **Human oversight** -- four-tier approval model from fully autonomous to human-required
- **Observability** -- OpenTelemetry tracing, structured logging, per-agent token budgets
- **Cloud-agnostic** -- runs on AWS, GCP, Azure, or on-premises

## Quick Links

- [Getting Started](getting-started.md) -- installation and first run
- [Architecture](architecture.md) -- system design overview
- [API Reference](api/index.md) -- auto-generated from source code
- [Software Requirements Specification](Colette_Software_Requirements_Specification.md) -- 164 requirements across 16 domains
