# Forum

This file provides guidance to Claude Code when working in this repository.

Forum is an AI-powered alternative data platform for trading and investment firms. Analysts plug in a URL, describe what they need, and agents build self-healing extraction pipelines that deliver structured data on a schedule.

## Architecture

Monorepo managed by Turborepo (JS/TS) and uv workspaces (Python).

```
apps/api/          → FastAPI backend (pipeline CRUD, auth, billing, compliance)
apps/web/          → React + TypeScript dashboard (Vite)
apps/site/         → Marketing site (Astro)
packages/agents/   → LLM orchestrator + sub-agents + tool registry (Python)
packages/pipeline/ → E-C-T-V-L-N runtime executed in ECS Fargate containers (Python)
packages/browser/  → Playwright automation, anti-detection, proxy management (Python)
packages/schemas/  → Shared Pydantic models used by API, agents, pipeline, SDKs
packages/sdk-python/   → Python SDK (PyPI: forum-sdk)
packages/sdk-typescript/ → TypeScript SDK (npm: @forum/sdk)
packages/cli/      → CLI tool (wraps sdk-python)
infra/terraform/   → All IaC (VPC, ECS, MWAA, RDS, S3, IAM, Cognito)
internal/          → Internal CLI (forum-internal), debug utilities, scripts
dags/              → Jinja2 YAML DAG templates for MWAA Serverless
docs/              → Documentation site (Mintlify)
```

Each subdirectory has (or should have) its own CLAUDE.md with package-specific context.

## Key Concepts

- **Code generation, not black-box LLM extraction.** Agents generate real Playwright scripts during setup. Scheduled runs execute that code deterministically — no LLM calls at runtime.
- **E-C-T-V-L-N pipeline stages:** Extract → Cleanse → Transform → Validate → Load → Notify. The `STAGE` env var controls which stage runs.
- **Code artifacts live in S3** at `tenants/{tenant_id}/pipelines/{pipeline_id}/code/v{n}/`. Every change is immutable and versioned. `latest` pointer determines active version.
- **Self-healing:** Change Detection Agent monitors for DOM changes → triggers Extraction Agent to regenerate code → validates against historical output → promotes if passing.
- **Adaptive stealth:** 4 levels (None → Basic → Standard → Aggressive), auto-calibrated per-pipeline during setup, auto-escalated at runtime on detection signals.
- **Multi-tenancy:** Schema-per-tenant in Postgres. Per-tenant IAM roles for MWAA workflows. Secrets Manager namespaced by tenant.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Frontend | React, TypeScript, Vite, TailwindCSS |
| Agents | LangGraph (or custom FSM), Playwright, LLM Gateway |
| Pipeline runtime | Python, Playwright, runs in ECS Fargate |
| Orchestration | MWAA Serverless (Free/Self-Service), MWAA Provisioned (Enterprise) |
| Infrastructure | Terraform, ECS Fargate, RDS Postgres, S3, Cognito, Secrets Manager |
| SDKs | Python (httpx), TypeScript (fetch) — both auto-generated from OpenAPI |

## Common Commands

```bash
# Local infrastructure
cd internal/debug && docker-compose up -d   # Postgres, Redis, LocalStack

# API
cd apps/api && FORUM_ENV=local uvicorn src.main:app --reload

# Pipeline (run a stage locally)
cd packages/pipeline
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=extract python -m pipeline.runner
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=all python -m pipeline.runner

# Agent setup (local, no DB side effects)
cd packages/agents
FORUM_ENV=local python -m agents.orchestrator --url "https://example.com" --description "Extract prices"

# Tests (per-package)
cd packages/pipeline && pytest
cd packages/agents && pytest
cd packages/schemas && pytest
cd apps/api && pytest
cd apps/web && npm test

# Monorepo-wide
turbo run test          # All packages in parallel
turbo run lint          # Lint everything
turbo run type-check    # Type-check everything

# Internal CLI
forum-internal code pull --tenant acme --pipeline pip_cme_settlements
forum-internal replay --run run_abc123
forum-internal trace view --run run_abc123
forum-internal agent heal --tenant acme --pipeline pip_cme_settlements --error-context "..."
```

## Debugging Flows

**Pipeline stage failing:**
1. `forum-internal pipeline runs --tenant X --pipeline Y --last 10` — check recent run status
2. `forum-internal pipeline logs --tenant X --run run_abc` — read error logs
3. `forum-internal trace view --run run_abc` — open Playwright trace (screenshots + DOM + network)
4. `forum-internal replay --run run_abc` — reproduce locally with exact artifacts
5. Fix code → `forum-internal replay --run run_abc --override-code ./fix.py` — test fix against same inputs

**Extraction code broken (site changed):**
1. `forum-internal code pull --tenant X --pipeline Y` — pull current code to `./debug/workspace/`
2. `forum-internal code diff --tenant X --pipeline Y --from v1 --to v2` — compare versions
3. Edit locally → `forum-internal code test --tenant X --pipeline Y --file ./fix.py`
4. `forum-internal code push --tenant X --pipeline Y --file ./fix.py --note "reason"`

**When FORUM_ENV=local:** S3 → local filesystem, Secrets Manager → .env file, RDS → local Postgres.

## Conventions

- **Python:** Pydantic for all data models. Async where I/O bound. Type hints everywhere.
- **Imports:** `packages/schemas/` is the single source of truth for shared types. API, agents, pipeline, and SDKs all import from it.
- **Errors:** Use the error taxonomy in `packages/schemas/src/forum_schemas/models/errors.py` (SOURCE_UNAVAILABLE, ACCESS_BLOCKED, SCHEMA_MISMATCH, etc.).
- **Tests:** Every package has its own `tests/` directory. Tests run via pytest (Python) or vitest/jest (TS). CI runs all in parallel via Turborepo.
- **Docker images tagged with git SHA**, never `latest`. Task definitions reference specific image tags.
- **Terraform:** Same modules for dev/staging/prod — only variable files differ. Never manual console changes.
- **Code artifacts:** Never overwrite — always create a new immutable version. Self-healing won't auto-overwrite human-edited code.
- **SDKs:** Auto-generated from OpenAPI spec. Hand-written convenience layers on top.
- **DAGs:** YAML + Jinja2 templates, generated programmatically by `dag_generator.py`. Never hand-edit rendered DAGs.

## AWS Deployment Map

| Component | Service | Source |
|-----------|---------|--------|
| API | App Runner or ECS Fargate + ALB | apps/api/ |
| Dashboard | S3 + CloudFront | apps/web/ |
| Pipeline Runner | ECS Fargate (launched by MWAA) | packages/pipeline/ |
| Agent Setup | ECS Fargate (launched by API) | packages/agents/ |
| Database | RDS PostgreSQL | infra/terraform/modules/rds/ |
| Orchestration | MWAA Serverless / Provisioned | infra/terraform/modules/mwaa/ |
| Storage | S3 | infra/terraform/modules/s3/ |
| Auth | Cognito | infra/terraform/modules/cognito/ |
| Secrets | Secrets Manager | infra/terraform/modules/secrets/ |