# Forum — Codebase Architecture

## 1. Monorepo Structure

Single monorepo. At Forum's stage (small team, tightly coupled services, shared types between API/agents/SDK), a monorepo avoids the overhead of cross-repo versioning and dependency management. Use [Turborepo](https://turbo.build/repo) or [Nx](https://nx.dev/) for task orchestration across packages (parallel builds, caching, dependency-aware task ordering). Python packages managed with a workspace-aware tool (e.g., `uv` workspaces or `hatch`).

```
forum/
│
├── CLAUDE.md                  # Project context, conventions, architecture overview for Claude Code
├── .claude/
│   ├── commands/              # Custom slash commands for common dev workflows
│   │   ├── new-agent.md           # /new-agent — scaffold a new sub-agent
│   │   ├── new-connector.md       # /new-connector — scaffold a new destination connector
│   │   ├── new-stage.md           # /new-stage — scaffold a new pipeline stage
│   │   ├── new-transform.md       # /new-transform — scaffold a pre-built transform action
│   │   └── debug-pipeline.md      # /debug-pipeline — pull and inspect a pipeline's artifacts
│   └── agents/                # Agent configurations for multi-step Claude Code workflows
│       ├── code-review.md
│       └── pipeline-test.md
│
├── apps/
│   ├── api/                   # FastAPI backend — the core platform service
│   ├── web/                   # React dashboard — the user-facing app
│   └── site/                  # Landing page / marketing site
│
├── packages/
│   ├── agents/                # All agent code (orchestrator, sub-agents, tool registry)
│   ├── pipeline/              # The ETV(L)N pipeline runtime
│   ├── browser/               # Playwright automation, proxy config, anti-detection
│   ├── schemas/               # Shared types, schema registry logic, validation rules
│   ├── sdk-python/            # Python SDK (published to PyPI as forum-sdk)
│   ├── sdk-typescript/        # TypeScript SDK (published to npm as @forum/sdk)
│   └── cli/                   # CLI tool (wraps sdk-python)
│
├── infra/
│   ├── terraform/             # All IaC (VPC, ECS, MWAA, RDS, S3, IAM, etc.)
│   └── docker/                # Dockerfiles
│
├── dags/                      # YAML DAG templates for MWAA Serverless
│
├── docs/                      # Documentation site (Mintlify or Docusaurus)
│
├── internal/                  # Internal tooling (not shipped to customers)
│   ├── cli/                   # Internal CLI for debugging and ops
│   ├── debug/                 # Debugging utilities and local replay
│   └── scripts/               # One-off scripts, migrations, seed data
│
├── .github/
│   └── workflows/             # CI/CD (GitHub Actions)
│
├── pyproject.toml             # Root Python workspace config
├── package.json               # Root JS/TS workspace config (for web, site, sdk-ts)
└── turbo.json                 # Turborepo pipeline config
```

---

## 2. Directory Detail

### 2.1 `apps/api/` — Platform API

The core backend service. Handles all platform capabilities: pipeline CRUD, schema management, user auth, billing, compliance, notifications, and webhook subscriptions. Serves both the web dashboard and the public REST API (they hit the same endpoints).

```
apps/api/
├── src/
│   ├── main.py                # FastAPI app entry point
│   ├── config.py              # Environment-aware config (local, staging, prod)
│   ├── routes/
│   │   ├── pipelines.py       # /v1/pipelines — CRUD, run, backfill, data access
│   │   ├── extract.py         # /v1/extract — adhoc one-time extraction
│   │   ├── sources.py         # /v1/sources — analyze, preview
│   │   ├── schemas.py         # /v1/schemas — schema template CRUD
│   │   ├── notifications.py   # /v1/notifications — subscription CRUD
│   │   ├── compliance.py      # /v1/compliance — rules, audit log, pre-check
│   │   ├── health.py          # /v1/pipelines/{id}/health, /v1/alerts
│   │   └── ws.py              # WebSocket endpoint for real-time events
│   ├── services/
│   │   ├── pipeline_service.py     # Business logic: create pipeline, generate DAG, trigger runs
│   │   ├── dag_generator.py        # Generates YAML DAGs from pipeline config → uploads to S3
│   │   ├── schema_service.py       # Schema versioning, breaking change detection, template management
│   │   ├── notification_service.py # Conditional notification evaluation, channel dispatch
│   │   ├── compliance_service.py   # Rule evaluation, PII detection, audit logging
│   │   ├── billing_service.py      # Credit metering, usage tracking, plan enforcement
│   │   └── mwaa_client.py          # Wrapper around MWAA Serverless API (create/update/start workflow)
│   ├── models/                # SQLAlchemy/Pydantic models (pipelines, runs, schemas, tenants, users)
│   ├── middleware/
│   │   ├── auth.py            # JWT/API key validation, tenant context injection
│   │   ├── tenant.py          # Per-request tenant isolation (sets Postgres search_path)
│   │   └── rate_limit.py      # Per-tenant rate limiting
│   └── db/
│       ├── migrations/        # Alembic migrations
│       └── session.py         # Database connection management
├── tests/
├── Dockerfile
└── pyproject.toml
```

**Deployment:** AWS App Runner (simplest) or ECS Fargate behind an ALB. Containerized. Auto-scales based on request volume.

### 2.2 `apps/web/` — User Dashboard

React + TypeScript SPA. Pipeline builder, monitoring dashboard, data explorer, schema editor, compliance center, billing/usage.

```
apps/web/
├── src/
│   ├── pages/
│   │   ├── pipelines/         # Pipeline list, creation wizard, detail view
│   │   ├── data/              # Data explorer (browse, filter, search extracted data)
│   │   ├── monitoring/        # Pipeline health grid, run history, alerts
│   │   ├── schemas/           # Schema template management
│   │   ├── compliance/        # Compliance rules, audit log, approval queue
│   │   ├── settings/          # Team, billing, API keys, notification channels
│   │   └── onboarding/        # First-run wizard
│   ├── components/
│   │   ├── pipeline-builder/  # Step-by-step pipeline creation (URL → schema → schedule → done)
│   │   ├── step-editor/       # Visual pipeline step editor (extract → transform → validate → load)
│   │   ├── code-viewer/       # Read-only code viewer for generated extraction code (enterprise)
│   │   ├── data-table/        # Paginated data table with CSV/JSON export
│   │   └── schema-builder/    # Visual schema field editor
│   ├── hooks/                 # React hooks (useWebSocket, usePipeline, useAuth, etc.)
│   ├── api/                   # Auto-generated API client from OpenAPI spec
│   └── lib/                   # Shared utilities
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

**Deployment:** Static build → S3 + CloudFront. Or AWS Amplify Hosting for simpler CI/CD.

### 2.3 `apps/site/` — Landing Page

Marketing site. Static. Next.js or Astro. Changelog, pricing, use cases, blog.

```
apps/site/
├── src/
│   ├── pages/
│   │   ├── index.astro        # Homepage
│   │   ├── pricing.astro
│   │   ├── use-cases/
│   │   ├── changelog/
│   │   └── blog/
│   └── components/
├── public/
└── package.json
```

**Deployment:** Vercel or Netlify. No AWS dependency — it's a static site. Marketing team can deploy independently.

---

### 2.4 `packages/agents/` — Agent Code

All LLM-powered logic: orchestrator, sub-agents, tool registry. Used during pipeline **setup** and **self-healing**, not during routine execution.

```
packages/agents/
├── src/
│   ├── orchestrator.py        # Main orchestrator (LangGraph state machine or custom FSM)
│   ├── agents/
│   │   ├── search.py          # Search Agent — page/API discovery, sitemap, llms.txt
│   │   ├── navigation.py      # Navigation Agent — Playwright codegen for multi-step flows
│   │   ├── form.py            # Form Interaction Agent — search forms, date pickers, login
│   │   ├── extraction.py      # Data Extraction Agent — selector generation, code output
│   │   ├── document.py        # Document Parsing Agent — PDF, Excel, CSV extraction
│   │   └── change_detection.py # Change Detection Agent — DOM diffing, structural hashing
│   ├── tools/                 # Tool registry (deterministic functions agents can call)
│   │   ├── browser.py         # navigate, click, type, scroll, screenshot
│   │   ├── dom.py             # get accessibility tree, extract text, find elements
│   │   ├── element.py         # Element resolution tools (wraps packages/browser/resolution/)
│   │   │                      #   find_by_text: locate elements by visible text (partial, case options)
│   │   │                      #   find_by_regex: locate elements by text pattern matching
│   │   │                      #   find_similar: find structurally similar elements (same template)
│   │   │                      #   adaptive_match: relocate element via stored fingerprint
│   │   │                      #   generate_selector: auto-produce CSS/XPath from any found element
│   │   │                      #   save_fingerprint: persist element fingerprint for future matching
│   │   ├── data.py            # parse JSON/CSV/PDF, validate schema, detect PII
│   │   ├── infra.py           # store to S3, write DAG, trigger pipeline
│   │   └── compliance.py      # check robots.txt, verify TOS, check source blacklist
│   ├── prompts/               # Versioned prompt templates per agent
│   │   ├── extraction_v1.txt
│   │   └── navigation_v1.txt
│   ├── nav_modes/             # Navigation mode implementations
│   │   ├── single_page.py     # Deterministic single-page extraction
│   │   ├── paginated.py       # Deterministic pagination handling
│   │   ├── list_detail.py     # List + detail page navigation
│   │   ├── multi_step.py      # URL template iteration
│   │   ├── api_discovery.py   # Network sniffing, API endpoint detection
│   │   └── agentic.py         # Full orchestrator → sub-agent pipeline
│   └── llm_gateway.py         # LLM Gateway client (model routing, caching, budget checks)
├── tests/
└── pyproject.toml
```

**Not deployed as a service.** This code is imported by:
1. `apps/api/` — when a user creates a pipeline (the API triggers agent pipeline setup)
2. `packages/pipeline/` — when self-healing is triggered during execution (Tier 4 of the resolution cascade)

The `tools/element.py` module wraps `packages/browser/resolution/` and exposes element resolution capabilities (find_by_text, find_similar, adaptive fingerprint matching, selector auto-generation) as callable tools that agents use during setup. The same resolution engine is also called directly by `packages/pipeline/` at runtime when selectors fail — agents are only invoked at Tier 4 (LLM semantic relocation) after deterministic methods are exhausted.

### 2.5 `packages/pipeline/` — EC-T-V-L-N Pipeline Runtime

The runtime that every ECS Fargate container executes. Pipeline stages run as **E-C-T-V-L-N**: Extract → Cleanse → Transform → Validate → Load → Notify. This is the bridge between agent-generated artifacts and actual data delivery. When MWAA triggers an `EcsRunTaskOperator`, the container starts and runs code from this package.

```
packages/pipeline/
├── src/
│   ├── runner.py              # Entry point — dispatches to the right stage based on STAGE env var
│   ├── context.py             # Per-run context (tenant, pipeline, credentials, schema, code version)
│   ├── stages/
│   │   ├── extract.py         # Pulls agent-generated code from S3, executes via Playwright
│   │   │                      #   Integrates resolution cascade (packages/browser/resolution/)
│   │   │                      #   On selector failure: fingerprint → content → LLM escalation
│   │   ├── cleanse.py         # NEW: Noise removal between extraction and transformation
│   │   │                      #   Strip HTML boilerplate, nav elements, ads, promo content
│   │   │                      #   Remove header/footer rows from data tables
│   │   │                      #   Extract footnote markers into qualifier metadata
│   │   │                      #   Whitespace/encoding normalization
│   │   │                      #   Dedup rows from pagination overlap
│   │   ├── transform.py       # Runs transform functions (pre-built + custom + agent-based formatting)
│   │   ├── validate.py        # System quality checks + user-defined rules + plausibility + confidence
│   │   ├── load.py            # Delivers data to configured destinations
│   │   └── notify.py          # Evaluates conditional notification rules, dispatches alerts
│   ├── transforms/            # Pre-built transform actions (deterministic, no LLM)
│   │   ├── normalize_dates.py
│   │   ├── convert_currency.py
│   │   ├── pct_change.py
│   │   ├── pivot.py
│   │   ├── deduplicate.py
│   │   └── cast_types.py
│   ├── formatting/            # NEW: Agent-based formatting (LLM-compiled to deterministic rules)
│   │   ├── rules.py           # Rule engine: load compiled formatting rules from S3, apply
│   │   ├── compiler.py        # Compile LLM-generated formatting logic into deterministic functions
│   │   └── fallback.py        # When compiled rules don't match a new pattern, invoke LLM → recompile
│   ├── connectors/            # Destination connectors
│   │   ├── s3.py
│   │   ├── snowflake.py
│   │   ├── redshift.py
│   │   ├── bigquery.py
│   │   ├── postgres.py
│   │   ├── webhook.py
│   │   └── base.py            # Connector interface
│   ├── validation/
│   │   ├── system_checks.py   # Row count anomalies, schema violations, distribution shifts
│   │   ├── user_rules.py      # User-defined rule evaluation engine
│   │   ├── quality.py         # Data quality scoring
│   │   ├── confidence.py      # NEW: Per-field confidence scoring (source grounding)
│   │   │                      #   Score based on: selector specificity, structural match,
│   │   │                      #   historical consistency, extraction method
│   │   │                      #   High (≥0.9) → load. Medium (0.6-0.9) → warn. Low (<0.6) → configurable
│   │   └── plausibility.py    # NEW: Silent failure detection
│   │                          #   Row count stability vs. rolling window
│   │                          #   Value distribution shift (mean, σ)
│   │                          #   Cardinality change detection
│   │                          #   Type consistency across runs
│   │                          #   Null rate spike detection
│   │                          #   Format consistency checks
│   ├── grounding.py           # NEW: Source grounding metadata generation
│   │                          #   Per-field provenance: URL, selector, screenshot region, timestamp
│   │                          #   Stored alongside run results in S3
│   └── tracing.py             # Playwright trace capture on failure (for debugging)
├── tests/
├── Dockerfile                 # → infra/docker/pipeline-runner.Dockerfile (or symlink)
└── pyproject.toml
```

**How it works at runtime:**

```
MWAA Serverless triggers EcsRunTaskOperator
  → ECS Fargate starts container from ECR image (packages/pipeline + Playwright + Chromium)
  → Container receives env vars: TENANT_ID, PIPELINE_ID, STAGE, CODE_VERSION, RUN_ID
  → runner.py reads STAGE, dispatches to the appropriate stage module
  → Stage pulls artifacts from S3 (extraction code, schema, transform rules, cleansing rules, formatting rules)
  → Stage pulls credentials from Secrets Manager (tenant-scoped)
  → Stage executes the E-C-T-V-L-N sequence:
      Extract  → run agent-generated Playwright code, capture raw data + source grounding metadata
                  On selector failure: tiered resolution cascade (fingerprint → content → LLM)
                  Resolution tier recorded in source grounding metadata per field
      Cleanse  → strip boilerplate, extract footnote qualifiers, normalize whitespace, dedup
      Transform → apply pre-built transforms + custom transforms + agent-based formatting rules
      Validate → system checks + user rules + confidence scoring + plausibility checks
      Load     → deliver to configured destinations (S3, Snowflake, webhook, etc.)
      Notify   → evaluate conditional notification rules, dispatch alerts
  → Container exits
```

**Running locally (for development/debugging):**

```bash
cd packages/pipeline

# Run a specific stage
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme CODE_VERSION=latest STAGE=extract \
  python -m pipeline.runner

# Run the full E-C-T-V-L-N sequence
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=all \
  python -m pipeline.runner

# Run just cleanse + transform (useful for debugging formatting issues)
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=cleanse,transform \
  python -m pipeline.runner --input ./debug/output/raw_extract.json
```

When `FORUM_ENV=local`, the context module swaps AWS dependencies for local equivalents: local filesystem instead of S3, `.env` file instead of Secrets Manager, local Postgres for results.

**Deployment:** Docker image pushed to ECR. Referenced by all `EcsRunTaskOperator` task definitions. Single image handles all stages — the `STAGE` env var determines which code path runs.

### 2.6 `packages/browser/` — Browser Automation & Anti-Detection

Playwright wrapper with 4-layer anti-detection, proxy management, device profiles, response caching, tiered element resolution, and trace capture. Shared by both `packages/agents/` (during setup) and `packages/pipeline/` (during extraction). This is Forum's stealth and extraction resilience infrastructure.

```
packages/browser/
├── src/
│   ├── browser.py             # Browser lifecycle: launch, configure, teardown
│   │                          #   Supports multiple browser builds:
│   │                          #   - Standard Chromium (permissive sources)
│   │                          #   - Patched Chromium (realistic TLS fingerprint)
│   │                          #   - Camoufox / Firefox (stealth-optimized fork)
│   │                          #   Tab pooling: max_tabs parameter for multi-page sessions
│   │                          #   Resource blocking: configurable font/image/stylesheet/domain filtering
│   ├── http.py                # curl_cffi HTTP client for non-browser requests
│   │                          #   JA3/JA4 TLS fingerprint impersonation (Chrome, Firefox, Safari, Edge)
│   │                          #   HTTP/2 and HTTP/3 (QUIC) support
│   │                          #   Version-specific profiles (chrome126, safari17_0, etc.)
│   │                          #   Replaces httpx/requests for stealth level "None"
│   │                          #   Used by: API Discovery mode, Monitor Pipelines, health checks
│   ├── proxy.py               # Proxy rotation (Bright Data / SmartProxy)
│   │                          #   Geo-location selection per-pipeline
│   │                          #   Datacenter + residential pool management
│   │                          #   Proxy health monitoring & failover
│   ├── stealth/
│   │   ├── calibrator.py      # Adaptive stealth calibration
│   │   │                      #   Probes source with increasing stealth levels during setup
│   │   │                      #   Records minimum required level in pipeline config
│   │   │                      #   Auto-escalates at runtime if detection signals appear
│   │   ├── profiles.py        # Cohort-based device profiles
│   │   │                      #   Library of real device fingerprints (screen, fonts, WebGL, etc.)
│   │   │                      #   Internally consistent profiles (timezone matches geo, fonts match OS)
│   │   │                      #   Persistent profile assignment per-pipeline
│   │   ├── tls.py             # TLS fingerprint management
│   │   │                      #   Match TLS client hello to claimed browser/OS
│   │   │                      #   HTTP/2 settings, header ordering, accept-encoding consistency
│   │   ├── behavior.py        # Human-like behavioral simulation
│   │   │                      #   Bezier curve mouse movements with acceleration/deceleration
│   │   │                      #   Log-normal timing distributions between actions
│   │   │                      #   Variable scroll with momentum, occasional overshoot
│   │   │                      #   Exploratory interactions (hover, pause, idle)
│   │   │                      #   Keypress simulation with realistic inter-key delays
│   │   ├── session.py         # Session-level stealth
│   │   │                      #   Session warming (visit homepage, accept cookies, navigate)
│   │   │                      #   Persistent browser profiles (cookies, localStorage across runs)
│   │   │                      #   Referrer chain construction (realistic entry paths)
│   │   │                      #   Schedule jitter (±1-15 min configurable per-pipeline)
│   │   └── signals.py         # Detection signal monitoring
│   │                          #   Detect challenge pages, throttling, soft blocks, honeypots
│   │                          #   Log signals per-run, feed back into calibrator
│   │                          #   Auto-escalate stealth level on detection
│   ├── resolution/            # Tiered element resolution cascade (see bible.md §5.6)
│   │   ├── cascade.py         # Resolution orchestrator: selector → fingerprint → content → LLM
│   │   │                      #   Called by pipeline runner when selectors fail at runtime
│   │   │                      #   Called by agents during setup for robust element location
│   │   │                      #   Returns resolved element + resolution tier metadata
│   │   ├── fingerprints.py    # Adaptive element fingerprinting (save/match/score)
│   │   │                      #   Stores: tag, text, attributes, siblings, ancestor path
│   │   │                      #   Multi-dimensional similarity scoring for relocation
│   │   │                      #   ~2-5ms per match, handles class renames / attribute changes
│   │   ├── similarity.py      # Structural similarity engine
│   │   │                      #   find_similar: given reference element, find all with same template
│   │   │                      #   find_by_text: locate by visible text content (partial, case options)
│   │   │                      #   find_by_regex: locate by text pattern matching
│   │   │                      #   generate_selector: auto-produce CSS/XPath from any found element
│   │   └── storage.py         # Pluggable fingerprint storage adapter
│   │                          #   Default: Redis (tenant-scoped keys: tenant:pipeline:element_id)
│   │                          #   Local dev: SQLite (FORUM_ENV=local)
│   │                          #   Interface: save(element, identifier), retrieve(identifier)
│   ├── cache.py               # Response caching layer
│   │                          #   Level 1: intra-tenant (tenant:url:region:time_bucket)
│   │                          #   Redis hot cache, S3 cold storage
│   │                          #   Tenant-scoped, encrypted at rest
│   ├── network.py             # Network interception, XHR/fetch sniffing (for API discovery)
│   ├── resource_filter.py     # Resource blocking configuration
│   │                          #   Block fonts, images, media, stylesheets, beacons by type
│   │                          #   Block specific domains (ad networks, analytics, anti-bot tracking)
│   │                          #   Subdomain auto-matching on blocked domains
│   │                          #   Configurable per-pipeline (some sources need CSS for layout)
│   │                          #   ~25% faster page loads, significant bandwidth savings
│   ├── tab_pool.py            # Rotating tab pool for multi-page sessions
│   │                          #   Reuses single browser instance with configurable max_tabs
│   │                          #   Avoids cold-start cost (~2-4s per browser launch)
│   │                          #   Manages tab lifecycle: open, reuse, rotate to prevent memory leaks
│   │                          #   Shared or isolated BrowserContexts per tab (configurable)
│   │                          #   Used by: Paginated List, List+Detail, Multi-Step nav modes
│   ├── tracing.py             # Playwright trace capture (screenshots, DOM snapshots, network log)
│   └── utils.py               # Wait helpers, retry logic, element interaction patterns
├── profiles/                  # Device profile library (JSON, checked into repo)
│   ├── windows_chrome.json    # Real device fingerprints: Windows + Chrome combinations
│   ├── macos_chrome.json      # Real device fingerprints: macOS + Chrome combinations
│   ├── macos_safari.json      # Real device fingerprints: macOS + Safari combinations
│   └── linux_firefox.json     # Real device fingerprints: Linux + Firefox combinations
├── tests/
└── pyproject.toml
```

**Stealth levels (configured per-pipeline, auto-calibrated during setup):**

| Level | Active Components | Typical Sources |
|-------|------------------|-----------------|
| None | `curl_cffi` HTTP with JA3/JA4 TLS impersonation, HTTP/3, stealthy headers (no browser) | Public APIs, direct file downloads, API Discovery, Monitor Pipelines |
| Basic | Headless browser, datacenter proxy, resource blocking (fonts/images/stylesheets stripped), tab pooling | Government portals, basic exchange sites |
| Standard | + TLS spoofing, device profiles, basic behavioral patterns, residential proxy | Cloudflare/Akamai protected sites |
| Aggressive | + Full behavioral simulation, session warming, persistent profiles, referrer chains | DataDome, PerimeterX, custom anti-bot |

### 2.7 `packages/schemas/` — Shared Types & Schema Logic

Shared across the entire monorepo. Defines the data models, schema registry logic, and validation rule types that the API, agents, pipeline runtime, and SDKs all use.

```
packages/schemas/
├── src/
│   ├── models/
│   │   ├── pipeline.py        # Pipeline, PipelineRun, PipelineConfig
│   │   ├── schema.py          # ExtractionSchema, SchemaVersion, SchemaTemplate
│   │   ├── tenant.py          # Tenant, Workspace, User, Role
│   │   ├── notification.py    # NotificationSubscription, Condition, Channel
│   │   ├── compliance.py      # ComplianceRule, AuditLogEntry
│   │   ├── errors.py          # Error taxonomy (SOURCE_UNAVAILABLE, ACCESS_BLOCKED, etc.)
│   │   └── variables.py       # PipelineVariable (String, List, Secret types)
│   ├── registry.py            # Schema versioning logic (breaking change detection, promotion)
│   └── builder.py             # Fluent schema builder API (used by SDK)
├── tests/
└── pyproject.toml
```

### 2.8 `packages/sdk-python/` — Python SDK

Primary SDK. Published to PyPI as `forum-sdk`. Auto-generated API client from OpenAPI spec, plus hand-written convenience layers (schema builder, real-time events, adhoc extraction).

```
packages/sdk-python/
├── src/
│   ├── forum/
│   │   ├── client.py          # ForumClient — main entry point
│   │   ├── pipelines.py       # Pipeline CRUD, run, data access
│   │   ├── extraction.py      # Adhoc extraction: client.extract_once(url, schema)
│   │   ├── schemas.py         # Schema template management + SchemaBuilder
│   │   ├── notifications.py   # Notification subscription management
│   │   ├── realtime.py        # WebSocket/SSE client for real-time events
│   │   ├── monitor.py         # Monitor pipeline convenience methods
│   │   └── generated/         # Auto-generated from OpenAPI spec (httpx-based)
│   └── forum_cli/             # CLI entry point (or separate packages/cli/)
│       ├── main.py            # Click/Typer CLI app
│       └── commands/
│           ├── pipeline.py    # forum pipeline create/list/run/data/logs/health
│           ├── extract.py     # forum extract --url <url>
│           ├── monitor.py     # forum monitor create --url <url>
│           └── auth.py        # forum auth login
├── tests/
└── pyproject.toml
```

### 2.9 `packages/sdk-typescript/` — TypeScript SDK

Published to npm as `@forum/sdk`. Auto-generated from the same OpenAPI spec. Ships after Python SDK.

### 2.10 `packages/cli/` — CLI

If the CLI grows large enough to warrant separation from `sdk-python`, it moves here. Otherwise, it lives inside `sdk-python` as shown above. Start inside `sdk-python`, extract if needed.

---

### 2.11 `infra/` — Infrastructure as Code

```
infra/
├── terraform/
│   ├── modules/
│   │   ├── vpc/               # VPC, subnets, NAT gateway, security groups
│   │   ├── ecs/               # ECS cluster, task definitions, ECR repos
│   │   ├── mwaa/              # MWAA Serverless environment config
│   │   ├── rds/               # PostgreSQL (RDS), parameter groups, backups
│   │   ├── s3/                # Buckets (data, DAGs, artifacts, audit logs)
│   │   ├── iam/               # Roles, policies (per-tenant, per-service)
│   │   ├── cognito/           # User pools, app clients, SSO config
│   │   ├── secrets/           # Secrets Manager namespace setup
│   │   ├── monitoring/        # CloudWatch dashboards, alarms, X-Ray
│   │   ├── app-runner/        # API service deployment (or ecs-service/ if using ECS for API)
│   │   └── tenant-env/        # Per-tenant environment provisioning (Enterprise Dedicated)
│   ├── environments/
│   │   ├── dev/               # Dev environment variables
│   │   ├── staging/           # Staging environment variables
│   │   └── prod/              # Production environment variables
│   ├── main.tf                # Root module composition
│   ├── variables.tf
│   └── outputs.tf
├── docker/
│   ├── pipeline-runner.Dockerfile   # packages/pipeline + Playwright + Chromium
│   ├── api.Dockerfile               # apps/api
│   └── agent-setup.Dockerfile       # packages/agents (if run as separate service)
└── scripts/
    ├── deploy.sh              # Deploy all services
    ├── seed-dev.sh            # Seed dev environment with test data
    └── rotate-secrets.sh      # Credential rotation helper
```

### 2.12 `dags/` — MWAA DAG Templates

YAML templates that `apps/api/services/dag_generator.py` renders when a user creates a pipeline. These are Jinja2-templated YAML files uploaded to S3 for MWAA Serverless consumption.

```
dags/
├── templates/
│   ├── extraction_pipeline.yaml.j2      # Standard ETV(L)N pipeline
│   ├── monitor_pipeline.yaml.j2         # Change detection (monitor-only) pipeline
│   └── hybrid_pipeline.yaml.j2          # Monitor + conditional extraction
└── examples/
    ├── cme_settlements.yaml             # Example rendered DAG for reference
    └── sec_edgar_filings.yaml
```

### 2.13 `docs/` — Documentation Site

```
docs/
├── introduction.mdx
├── quickstart.mdx
├── guides/
│   ├── navigation-modes.mdx
│   ├── schemas.mdx
│   ├── variables.mdx
│   ├── monitor-pipelines.mdx
│   ├── notifications.mdx
│   └── compliance.mdx
├── api-reference/             # Auto-generated from OpenAPI spec
├── sdk/
│   ├── python.mdx
│   ├── typescript.mdx
│   └── cli.mdx
└── mint.json                  # Mintlify config (or docusaurus.config.js)
```

**Deployment:** Mintlify (managed, auto-deploys from repo) or Docusaurus on Vercel.

---

## 3. Internal Tooling & Debugging

### 3.1 `internal/cli/` — Internal Operations CLI

Not shipped to customers. Used by Forum engineers for pipeline debugging, tenant ops, and code artifact management.

```
internal/cli/
├── src/
│   ├── main.py                # Entry point: forum-internal <command>
│   └── commands/
│       ├── code.py            # Code artifact operations (pull, push, test, rollback, diff)
│       ├── pipeline.py        # Pipeline inspection (status, config, run history, logs)
│       ├── tenant.py          # Tenant ops (list, inspect, provision, migrate tier)
│       ├── replay.py          # Re-run a historical run with exact artifacts
│       ├── agent.py           # Manually trigger agent pipeline (setup, self-heal, regenerate)
│       └── trace.py           # Download and open Playwright traces for failed runs
├── pyproject.toml
└── README.md
```

**Key commands:**

```bash
# ─── Code Artifact Operations ───────────────────────────────────────

# Pull the current extraction code for a pipeline to local workspace
forum-internal code pull --tenant acme --pipeline pip_cme_settlements
# → Downloads to: ./debug/workspace/acme/pip_cme_settlements/
#    extract.py, transform.py, schema.json, config.json

# View code without downloading (prints to stdout)
forum-internal code show --tenant acme --pipeline pip_cme_settlements --version v2

# Diff two code versions
forum-internal code diff --tenant acme --pipeline pip_cme_settlements --from v1 --to v2

# Test an edited extraction script against the live source
forum-internal code test --tenant acme --pipeline pip_cme_settlements \
  --file ./debug/workspace/acme/pip_cme_settlements/extract.py

# Push edited code as a new version
forum-internal code push --tenant acme --pipeline pip_cme_settlements \
  --file ./debug/workspace/acme/pip_cme_settlements/extract.py \
  --note "Fixed selector for updated CME layout"

# Roll back to a previous version
forum-internal code rollback --tenant acme --pipeline pip_cme_settlements --version v2

# List all code versions for a pipeline
forum-internal code history --tenant acme --pipeline pip_cme_settlements
# → v1  2025-03-01  system:agent         Initial generation
#   v2  2025-03-10  system:self-heal     Auto-healed: CME layout change
#   v3  2025-03-11  user:eng@forum.com   Manual fix: timeout on slow load
#   v4  2025-03-15  system:self-heal     Auto-healed: new column detected


# ─── Pipeline Debugging ─────────────────────────────────────────────

# Inspect a pipeline's full config (schema, schedule, variables, destinations, etc.)
forum-internal pipeline inspect --tenant acme --pipeline pip_cme_settlements

# View recent run history with status, duration, row count, errors/warnings
forum-internal pipeline runs --tenant acme --pipeline pip_cme_settlements --last 10

# View detailed logs for a specific run
forum-internal pipeline logs --tenant acme --run run_abc123

# View the rendered YAML DAG for a pipeline
forum-internal pipeline dag --tenant acme --pipeline pip_cme_settlements


# ─── Run Replay ──────────────────────────────────────────────────────

# Re-run a specific historical run with its EXACT code version, schema, and inputs
# Runs locally — does not trigger MWAA or affect production
forum-internal replay --run run_abc123
# → Pulls code v2, schema v3, variables {"tickers": ["AAPL"]}
#   Executes extract → transform → validate locally
#   Writes results to ./debug/output/run_abc123/

# Replay with a modified code file (test a fix against the exact same inputs)
forum-internal replay --run run_abc123 \
  --override-code ./debug/workspace/acme/pip_cme_settlements/extract.py


# ─── Agent Operations ────────────────────────────────────────────────

# Manually trigger the agent to re-analyze a page and regenerate extraction code
forum-internal agent regenerate --tenant acme --pipeline pip_cme_settlements \
  --reason "Page layout changed, selectors broken"

# Trigger self-healing with additional context (e.g., error message from a failed run)
forum-internal agent heal --tenant acme --pipeline pip_cme_settlements \
  --error-context "TimeoutError: Waiting for selector '#settlement-table' exceeded 30s"

# Run the full agent setup pipeline for a new URL (without creating a pipeline in the DB)
forum-internal agent setup --url "https://www.cmegroup.com/..." --description "CME crude settlements"


# ─── Playwright Traces ───────────────────────────────────────────────

# Download trace for a failed run and open in Playwright trace viewer
forum-internal trace view --run run_abc123
# → Downloads s3://forum-data/tenants/acme/pipelines/pip_cme/debug/traces/run_abc123.zip
#   Opens: npx playwright show-trace trace.zip

# List available traces for a pipeline
forum-internal trace list --tenant acme --pipeline pip_cme_settlements


# ─── Tenant Operations ───────────────────────────────────────────────

# List all tenants with tier, pipeline count, last active
forum-internal tenant list

# Inspect a specific tenant (config, usage, pipelines, billing status)
forum-internal tenant inspect --tenant acme

# Migrate a tenant between tiers (updates IAM roles, MWAA config, etc.)
forum-internal tenant migrate --tenant acme --from self-service --to enterprise-base
```

### 3.2 `internal/debug/` — Local Debugging Utilities

```
internal/debug/
├── workspace/                 # Working directory for pulled code artifacts (gitignored)
├── output/                    # Output directory for replay results (gitignored)
├── docker-compose.yml         # Local stack: Postgres, Redis, LocalStack (S3/Secrets mock)
├── seed.py                    # Seed local DB with test tenants, pipelines, sample data
├── .env.example               # Template for local environment variables
└── README.md                  # How to set up local debugging environment
```

**Local development setup:**

```bash
# Start local infrastructure
cd internal/debug
cp .env.example .env           # Fill in API keys, test credentials
docker-compose up -d           # Postgres, Redis, LocalStack

# Seed with test data
python seed.py

# Run the API locally
cd ../../apps/api
FORUM_ENV=local uvicorn src.main:app --reload

# Run a pipeline stage locally
cd ../../packages/pipeline
FORUM_ENV=local TENANT_ID=test PIPELINE_ID=test_cme STAGE=extract \
  python -m pipeline.runner

# Run the full agent setup pipeline against a test URL
cd ../../packages/agents
FORUM_ENV=local python -m agents.orchestrator \
  --url "https://sandbox.forum.dev/ecommerce" \
  --description "Extract product prices"
```

### 3.3 Playwright Trace Capture

The pipeline runtime automatically captures Playwright traces on failure. Traces include screenshots, DOM snapshots, and network logs at every step — enabling full visual replay of what the browser did.

```python
# packages/pipeline/src/tracing.py

import os
from pathlib import Path
from contextlib import asynccontextmanager

@asynccontextmanager
async def traced_browser_context(playwright, run_context):
    """
    Wraps a Playwright browser context with trace capture.
    On success: discards trace (no overhead).
    On failure: saves trace to S3 for debugging.
    """
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    await context.tracing.start(screenshots=True, snapshots=True, sources=True)

    try:
        yield context
        # Success — stop tracing, discard
        await context.tracing.stop()
    except Exception:
        # Failure — save trace for debugging
        trace_path = f"/tmp/trace-{run_context.run_id}.zip"
        await context.tracing.stop(path=trace_path)

        # Upload to S3 for later retrieval
        s3_key = (
            f"tenants/{run_context.tenant_id}"
            f"/pipelines/{run_context.pipeline_id}"
            f"/debug/traces/{run_context.run_id}.zip"
        )
        run_context.s3_client.upload_file(trace_path, run_context.bucket, s3_key)
        raise
    finally:
        await browser.close()
```

### 3.4 ECS Exec (Live Container Debugging)

For debugging a running Fargate task in real-time, enable ECS Exec in the task definition:

```hcl
# infra/terraform/modules/ecs/task_definition.tf

resource "aws_ecs_task_definition" "pipeline_runner" {
  # ...
  enable_execute_command = true    # Enables ECS Exec (shell into running container)
}
```

Then connect to a running task:

```bash
aws ecs execute-command \
  --cluster forum-shared-cluster \
  --task <task-arn> \
  --container runner \
  --interactive \
  --command "/bin/bash"
```

This gives you a shell inside the running container — useful for inspecting state mid-execution, checking environment variables, testing selectors against the live page, etc. Use sparingly (it's a production container), but invaluable when something is broken and you need to see what's happening in real-time.

---

## 4. Code Artifact Lifecycle

Agent-generated code and human-edited code follow the same lifecycle. The system doesn't distinguish between them at execution time — both are versioned Python files in S3.

```
S3: forum-data/tenants/{tenant_id}/pipelines/{pipeline_id}/
├── code/
│   ├── v1/
│   │   ├── extract.py           # Agent-generated Playwright extraction logic
│   │   ├── transform.py         # Transform functions
│   │   └── metadata.json        # { author: "system:agent", created_at: "...", note: "Initial generation" }
│   ├── v2/
│   │   ├── extract.py           # Self-healed version
│   │   ├── transform.py
│   │   └── metadata.json        # { author: "system:self-heal", note: "CME layout change", parent: "v1" }
│   ├── v3/
│   │   ├── extract.py           # Human-edited version
│   │   ├── transform.py
│   │   └── metadata.json        # { author: "user:eng@forum.com", note: "Fixed timeout", parent: "v2" }
│   └── latest -> v3             # Symlink (or pointer in DB) to active version
├── schema/
│   ├── v1.json
│   └── v2.json
├── config.json                  # Schedule, variables, destinations, notifications, navigation mode
└── debug/
    └── traces/                  # Playwright trace files from failed runs
        ├── run_abc123.zip
        └── run_def456.zip
```

**Versioning rules:**
- Every code change creates a new immutable version (never overwrite)
- `metadata.json` tracks: author (system:agent | system:self-heal | user:{email}), creation timestamp, parent version, change note
- The pipeline runner always reads the `latest` pointer to determine which version to execute
- Rolling back = updating the `latest` pointer to a previous version
- Self-healing creates a new version but only auto-promotes if validation passes (see §12.2 in research doc)

**Human-edited code and self-healing coexistence:**
When an engineer edits code (creates a version with `author: "user:..."`) , the self-healing agent respects this by default — it won't auto-overwrite human edits. If the source changes and the human-edited code breaks, the agent generates a *candidate* version and flags it for human review rather than auto-promoting. The engineer can then merge the agent's changes into their custom code, or let the agent take over again by removing the human-owned flag.

---

## 5. CI/CD Pipeline

```
.github/workflows/
├── ci.yml                     # Runs on every PR: lint, type-check, test all packages
├── deploy-api.yml             # On merge to main: build + push API image → deploy to App Runner/ECS
├── deploy-pipeline.yml        # On merge to main: build + push pipeline-runner image → ECR
├── deploy-web.yml             # On merge to main: build React → deploy to S3/CloudFront
├── deploy-site.yml            # On merge to main: deploy marketing site to Vercel
├── deploy-infra.yml           # On merge to main (infra/ changes): terraform plan → apply
├── publish-sdk-python.yml     # On tag (sdk-python-v*): build + publish to PyPI
├── publish-sdk-typescript.yml # On tag (sdk-ts-v*): build + publish to npm
└── deploy-docs.yml            # On merge to main (docs/ changes): deploy to Mintlify
```

**Key principles:**
- **Every package has its own tests.** CI runs all tests in parallel (Turborepo handles dependency ordering).
- **Docker images are tagged with git SHA.** The pipeline-runner image is `forum-pipeline-runner:{git-sha}`. Task definitions reference specific image tags, not `latest`.
- **Infrastructure changes require `terraform plan` output in PR review.** No blind `apply`.
- **SDKs are published on explicit version tags**, not on every merge. The SDK version is independent of the API version.

---

## 6. Deployment Map (AWS)

| Component | AWS Service | Source | Notes |
|-----------|-------------|--------|-------|
| Platform API | App Runner (or ECS Fargate + ALB) | `apps/api/` | Auto-scaling, HTTPS, custom domain |
| Web Dashboard | S3 + CloudFront | `apps/web/` | Static SPA, CDN-distributed |
| Marketing Site | Vercel | `apps/site/` | Not on AWS — simpler for marketing deploys |
| Docs | Mintlify (managed) | `docs/` | Auto-deploys from repo |
| Pipeline Runner | ECS Fargate (via MWAA) | `packages/pipeline/` | Docker image in ECR. Launched by EcsRunTaskOperator |
| Agent Setup | ECS Fargate (via API) | `packages/agents/` | Runs during pipeline creation. Could also run in API process for simple nav modes |
| DAGs | S3 (MWAA reads from here) | `dags/` | Rendered YAML uploaded by `dag_generator.py` |
| Database | RDS PostgreSQL | `infra/terraform/modules/rds/` | Schema-per-tenant |
| Cache | ElastiCache Redis | `infra/terraform/modules/redis/` | Semantic cache, session cache |
| Object Storage | S3 | `infra/terraform/modules/s3/` | Code artifacts, raw data, audit logs, traces |
| Auth | Cognito | `infra/terraform/modules/cognito/` | User pools, SSO/SAML |
| Secrets | Secrets Manager | `infra/terraform/modules/secrets/` | Per-tenant namespaced credentials |
| Orchestration | MWAA Serverless | `infra/terraform/modules/mwaa/` | Reads YAML DAGs from S3, triggers ECS tasks |
| Monitoring | CloudWatch + X-Ray | `infra/terraform/modules/monitoring/` | Metrics, alarms, tracing |

---

## 7. Key Design Principles

1. **A new developer reads the top-level directory names and understands where everything lives.** `apps/` = services. `packages/` = shared libraries. `infra/` = infrastructure. `internal/` = team tooling. `docs/` = documentation. No ambiguity.

2. **Separation follows deployment boundaries.** `packages/pipeline/` runs in ECS containers. `packages/agents/` runs during setup (in API or separate ECS task). `apps/api/` runs as a persistent service. They can import from each other within the monorepo, but they have clear ownership and distinct runtime environments.

3. **Agent-generated code and human-edited code are the same thing.** Both are versioned files in S3. The pipeline runner doesn't know or care who authored the code. This makes the system debuggable from day one and makes customer-facing code visibility (Phase 3) a pure UI feature, not an architectural change.

4. **Internal tooling is a first-class citizen.** The `internal/` directory and `forum-internal` CLI are not afterthoughts — they're how the team operates the platform daily. Investing in these tools from Phase 0 pays dividends immediately in debugging speed and operational confidence.

5. **Infrastructure is code, environments are config.** The same Terraform modules are used for dev, staging, and prod — only the variable files differ. No manual AWS console actions in production.
