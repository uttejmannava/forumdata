# Forum — Architecture Research Document

## 1. Thesis

Prices factor in reality faster than reality becomes obvious. Reality is non-stationary, constantly producing new information that changes how prices react. Information edge is renewable until we always know what the future holds — which is never.

Alternative data is what helps firms understand and/or predict price action. The least informative alt data is lagged and/or already consensus (financial statements, macro releases). The most informative alt data is sampled sooner and isn't broadly discovered.

Alt data naturally commoditizes: a firm discovers data or a signal → signal produces alpha → other firms discover it, a vendor productizes it → even more firms have access → alpha decays, signal becomes table stakes. Examples: credit card data, satellite imagery, app downloads/MAUs.

Truly renewable information edge is in data discovery and modelling. A static dataset only provides edge temporarily, is expected to be productized, and thus becomes replicable by peers. Owning the discovery process allows firms to constantly renew their moat and keep ideas protected internally. The best teams act like research labs, constantly generating and validating ideas faster than they can be commoditized. Some firms don't even subscribe to data catalogs, instead opting to purchase metadata (release schedules) and build their own pipelines.

---

## 2. The Problem

**Current process at most firms:**

1. Analyst/trader generates thesis, requests engineering resources (pod-allocated or the slower central data team)
2. Data compliance team approves the ask
3. Engineers build pipeline manually
4. Engineers maintain brittle pipeline that breaks constantly (website changes, API endpoints update)
5. Data quality issues (likely discovered downstream by analyst) require extra data validation, custom backfills
6. Further iterations add more downtime to data ingestion

**Core pain points:**

- Engineering talent is wasted on automation-worthy tasks, drawn away from higher-order work
- Engineering OpEx is high, not scalable as domains expand (crypto, prediction markets)
- Turnaround time from idea → data is measured in weeks, not hours
- Pipeline maintenance is a constant tax on engineering teams

---

## 3. Forum's Solution

A self-serve platform where analysts/traders can discover and operationalize public/web-based alternative data without engineering support.

**Workflow:**

1. Analyst/trader generates thesis, plugs URL into platform
2. Describes what is needed in natural language and/or as a schema
3. Agents are deployed, handling extraction, transformations, validations, and loading into team's databases
4. Dataset is created and updated on a schedule

**Value propositions:**

- No-code, putting power back in the hands of analysts/traders
- Workflow becomes research-like: discover data fast, test signals, iterate further or discard and move to the next idea
- Agents detect changes in websites, allowing pipelines to be self-healing
- Human engineers are hands-off, can monitor and dedicate time to other work

**For firms with existing data resources:** Forum drastically increases dataset turnaround time, so analysts can work like researchers.

**For firms without prior resources:** Forum removes manual data labor from analysts and lets them focus on signal extraction and modelling.

**Vertical-first approach:** Unlike horizontal scraping platforms (Kadoa, Diffbot, etc.) that serve marketers, recruiters, e-commerce, and every other vertical, Forum is built exclusively for trading and investment workflows. Every default, template, validation rule, and UI decision is optimized for alt-data use cases — financial schemas, market-relevant sources, compliance requirements for regulated firms. A vertical product can be 10x better for its target user because it never compromises for generality.

**Macro tailwind:** Public data (websites, APIs) will be increasingly readable by agents. Agent readability is being improved by semantic HTML, RESTful APIs, and standards like llms.txt.

---

## 4. Architecture Overview

### 4.1 System Layers

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                         │
│  Web UI (React) — pipeline builder, monitoring, compliance  │
│  CLI / SDK (Python + TypeScript)                            │
│  REST API — all platform capabilities exposed               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  API GATEWAY & AUTH                                         │
│  Amazon API Gateway (REST + WebSocket)                      │
│  Cognito / custom JWT — per-tenant auth, RBAC               │
│  Rate limiting, request validation, API key management      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────┬───────────▼──────────────┬───────────────────┐
│ ORCHESTRATION│                          │ PIPELINE ENGINE   │
│ Orchestrator │  Agent (task decomp.)    │ MWAA Serverless   │
│ Sub-agents:  │  Search, Navigate, Form, │  (Free/Self-Svc)  │
│              │  Extract, Parse, Monitor │ MWAA Provisioned  │
│ Agent Runtime│  LangGraph / custom FSM  │  (Enterprise Ded) │
└──────────────┴──────────────────────────┴───────────────────┘
                           │
┌──────────────┬───────────▼──────────────┬───────────────────┐
│ COMPUTE      │                          │ DATA & STORAGE    │
│ ECS Fargate  │  Containerized agents    │ RDS PostgreSQL    │
│ Playwright   │  Headless browsers       │ S3 (raw, audit)   │
│ Proxy layer  │  Residential + DC        │ Redis (state)     │
│ Lambda       │  Lightweight transforms  │ Customer delivery │
└──────────────┴──────────────────────────┴───────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  CROSS-CUTTING SERVICES                                     │
│  Compliance Engine — rule evaluation, PII detection, audit  │
│  Self-Healing Monitor — change detection, code regeneration │
│  LLM Gateway — model routing, cost tracking, caching        │
│  Tenant Control Plane — provisioning, billing, isolation    │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Key Architectural Decision: Code Generation, Not Black-Box LLM Extraction

Following Kadoa's model, agents generate and maintain real scraping code — not black-box LLM outputs. Every workflow runs deterministically, so results are consistent, explainable, and fully auditable.

- **Phase 1 — Setup (LLM-heavy):** Agents use LLMs to analyze the page, understand structure, infer schema, and generate extraction code. This happens once (or when the page changes). The output is a versioned Playwright script + selector definitions + transform functions stored as code artifacts.
- **Phase 2 — Execution (LLM-free):** The generated code runs on each scheduled pipeline execution. No LLM calls. Pure Playwright browser automation + data parsing. Per-run costs near zero, execution is deterministic.
- **Phase 3 — Maintenance (LLM-triggered):** When the Change Detection Agent flags a structural change, it triggers the Extraction Agent to regenerate code. The new code is validated against historical output before being promoted.

### 4.3 Browser Identity & Anti-Detection Strategy

Reliable extraction requires surviving modern anti-bot systems (Cloudflare, Akamai, DataDome, PerimeterX). Detection operates at four layers, and Forum must have countermeasures at each. Industry data shows that proxy-only approaches are now insufficient — detection has moved well beyond IP-level signals to TLS fingerprinting, behavioral analysis, and cross-session heuristics.

#### Layer 1 — Network-Level Signals

**What's detected:** IP reputation, request rate, geographic consistency, TLS fingerprint.

**Countermeasures:**
- **Proxy rotation** with residential + datacenter mix via Bright Data / SmartProxy, geo-targeted per-pipeline
- **TLS fingerprint spoofing** — headless Chromium has a trivially identifiable TLS client hello. Ship multiple browser builds: standard Chromium (for permissive sources), patched Chromium with realistic TLS fingerprint, and Camoufox (Firefox fork built for automation stealth). Rotate between them. The TLS fingerprint should match the claimed User-Agent (e.g., a Firefox TLS fingerprint paired with a Firefox UA string)
- **Protocol-level consistency** — HTTP/2 settings, header ordering, and accept-encoding values must match the claimed browser

#### Layer 2 — Browser-Level Fingerprinting

**What's detected:** Canvas rendering, WebGL renderer, audio context fingerprint, installed fonts, screen resolution, timezone, language, platform, hardware concurrency, device memory.

**Countermeasures:**
- **Cohort-based device profiles** rather than random spoofing. Maintain a library of real device profiles collected from actual browsers. Each profile is internally consistent — screen resolution matches viewport, timezone matches proxy geo-location, fonts match OS, WebGL renderer matches GPU plausibility for the claimed platform
- **Profile assignment:** Each session gets a consistent profile (not randomized per-page). A persistent profile ID is stored per-pipeline so the same "device" appears across runs
- **Canvas/WebGL noise injection** — add subtle, deterministic noise to canvas and WebGL outputs (seeded by profile ID so fingerprint is consistent within a session but unique across sessions)

#### Layer 3 — Behavioral Analysis

**What's detected:** Mouse movements, scroll patterns, click timing, navigation flow, idle time, keypress cadence.

**Countermeasures:**
- **Bezier curve mouse movements** with realistic acceleration/deceleration (not linear interpolation)
- **Log-normal timing distributions** for delays between actions (human reaction times follow log-normal, not uniform random)
- **Variable scroll behavior** — fast scrolls with occasional pauses, momentum-style deceleration, sometimes scroll past the target and scroll back
- **Exploratory interactions** — occasionally hover over irrelevant elements, move to the scrollbar, pause mid-page. These serve no extraction purpose but defeat behavioral pattern detectors
- **Keypress simulation** with realistic inter-key delays when typing (form fills, search inputs), including occasional pauses as if thinking

#### Layer 4 — Session-Level & Cross-Request Signals

**What's detected:** Empty cookie jars, missing referrer chains, regular request cadence, no prior site history, missing consent interactions.

**Countermeasures:**
- **Session warming** — before extracting, visit the homepage, accept cookie consent, click through 1-2 navigation links. Build a realistic session history. Adds a few seconds per run but dramatically reduces detection on sophisticated sites
- **Persistent browser profiles** — for sources hit on a recurring schedule, maintain a browser profile (cookies, localStorage, session storage) across runs. The scraper looks like a returning user, not a fresh visitor. Profiles stored encrypted in S3, tenant-scoped
- **Referrer chain construction** — arrive at the target page via a realistic referrer (Google search, bookmarks page, site navigation) rather than direct URL entry
- **Irregular scheduling** — don't run at exactly 06:00:00 every day. Add jitter (±1-15 minutes, configurable per-pipeline) so request timing doesn't form a detectable pattern

#### Adaptive Stealth Calibration

Not every source needs the same level of anti-detection. A government CSV download page wastes time on behavioral simulation. A Cloudflare-protected financial portal needs everything.

**Stealth levels:**

| Level | Countermeasures Active | Use When |
|-------|----------------------|----------|
| **None** | Direct HTTP request, no browser | Public APIs, direct file downloads, permissive `robots.txt` |
| **Basic** | Headless browser with default settings, datacenter proxy | Government portals, exchange sites with no anti-bot |
| **Standard** | TLS spoofing, device profiles, basic behavioral patterns, residential proxy | Sites with standard Cloudflare/Akamai protection |
| **Aggressive** | All 4 layers active: TLS spoofing, cohort profiles, full behavioral simulation, session warming, persistent profiles, residential proxy with geo-match | Sites with advanced anti-bot (DataDome, PerimeterX, custom solutions) |

**Auto-calibration:** During pipeline setup, the agent probes the target with increasing stealth levels. Start with None — if blocked, escalate to Basic, then Standard. Record the minimum stealth level that succeeds and store it in the pipeline config. During execution, if a previously-working level starts getting blocked (detection system upgraded), the pipeline runner automatically escalates one level and logs the change. If Aggressive fails, trigger self-healing and alert the user.

#### Detection Signal Monitoring

Instead of only reacting to hard failures (403, CAPTCHA page), actively detect *signs of detection before full blocking*:

| Signal | Detection Method | Response |
|--------|-----------------|----------|
| **Challenge page** | Content analysis: Cloudflare interstitial, DataDome CAPTCHA | Escalate stealth level, retry |
| **Throttling** | Response time >3x rolling average | Switch proxy, add delay |
| **Soft block** | 200 response but content differs from expected structure (honeypot) | Flag as potential honeypot, compare against known-good snapshot |
| **Cookie challenge** | Set-Cookie with challenge token + redirect loop | Enable session warming, retry with full browser |
| **Fingerprint probe** | Page loads unusual JS (canvas tests, WebGL queries) before showing content | Switch to Aggressive stealth, use cohort profile |
| **Rate limit warning** | 429 status or custom rate-limit headers | Back off, increase jitter, spread across proxy pool |

Detection signals are logged per-run and feed back into the adaptive stealth calibration. If a source accumulates detection signals over time, its default stealth level is permanently escalated.

#### Compliance-Aware Stealth Selection

The Compliance Engine feeds into stealth selection:
- If `robots.txt` is permissive and the site has no anti-bot → stealth level None or Basic
- If `llms.txt` is present and grants machine access → stealth level None (use the machine-readable interface directly)
- If `robots.txt` is restrictive but compliance officer has approved extraction → start at Standard (expect active defense)
- If the site actively serves `llms.txt` endpoints → prefer those over browser scraping (cheaper, faster, more reliable, no stealth needed)

---

## 5. Agentic Orchestration Layer

### 5.1 Orchestrator Agent

Receives user intent (URL + natural language description or schema). Analyzes the target source. Decomposes the task into a directed graph of sub-tasks. Selects which skill agents to invoke and in what order. Manages state transitions, retries, and error escalation. Produces a final pipeline artifact (DAG definition + extraction code + transform logic).

**Implementation:** Build as a LangGraph state machine (or custom Python FSM). The orchestrator maintains a structured state object:

```
PipelineState {
  source_url: str
  user_intent: str
  target_schema: Schema
  navigation_plan: List[NavigationStep]
  extraction_code: str
  transform_rules: List[TransformRule]
  validation_rules: List[ValidationRule]
  compliance_checks: ComplianceResult
  dag_definition: AirflowDAG
  status: enum
}
```

### 5.2 Skill Agents (Sub-Agents)

| Agent | Responsibility | Technology |
|-------|---------------|------------|
| **Search Agent** | Discovers relevant pages, sitemaps, API endpoints. Crawls link structures. Identifies pagination patterns. Produces page inventory. | Playwright + LLM for structure analysis |
| **Navigation Agent** | Generates browser automation code for multi-step navigation: clicking menus, handling auth walls, dropdowns, pagination. | Playwright codegen. LLM analyzes DOM/accessibility tree, generates action sequences. Outputs replayable scripts. |
| **Form Interaction Agent** | Handles search forms, date pickers, filters, login flows. Identifies form fields, fills programmatically. | DOM analysis + Playwright. LLM understands field semantics. |
| **Document Parsing Agent** | Extracts structured data from PDFs, Excel, CSVs linked on pages. OCR for scanned documents. Table extraction. | Apache Tika, Camelot/tabula-py, Textract for OCR, LLM for schema inference |
| **Data Extraction Agent** | Core extractor. Generates CSS/XPath selectors or code-based extraction logic from page analysis. Tests against multiple page variants. Produces deterministic extraction code. | LLM analyzes cleaned HTML to generate selectors. Validates against user schema. |
| **Change Detection Agent** | Monitors target pages for structural changes (DOM diffs), content updates, availability issues. Triggers self-healing. | Scheduled lightweight page fetches. DOM diffing (structural hash). Content hashing. |

### 5.3 Tool Registry

Each agent has access to a shared tool registry — callable functions that separate agent reasoning (LLM) from agent actions (deterministic tools):

- **Browser actions:** navigate, click, type, scroll, screenshot
- **DOM analysis:** get accessibility tree, extract text, find elements
- **Data tools:** parse JSON/CSV/PDF, validate schema, detect PII
- **Infrastructure tools:** store to S3, write DAG, trigger pipeline
- **Compliance tools:** check robots.txt, verify TOS, check source blacklist

### 5.4 Navigation Modes (Tiered Complexity)

Not every extraction requires the full agentic pipeline. Most jobs are simple — a single page with a table, or a paginated list. Running the full LLM-powered orchestrator for these is wasteful (LLM cost, latency, complexity). Navigation modes escalate from cheap/deterministic to expensive/agentic:

| Mode | Description | LLM Cost | Use Case |
|------|-------------|----------|----------|
| **Single Page** | Extract from one URL. No navigation. Deterministic selectors only. | Setup only | Static tables, single data pages, API JSON responses |
| **Paginated List** | Auto-detect and handle pagination (next buttons, infinite scroll, page parameters). Deterministic. | Setup only | Multi-page tables, search results, filings lists |
| **List + Detail** | Extract list, then navigate into each detail page for richer data. Deterministic once selectors are generated. | Setup only | Job boards, product catalogs, SEC EDGAR filing index → individual filings |
| **Multi-Step (Templated)** | URL templates with `%%` placeholders iterated over a provided value list. Deterministic. | Setup only | Same scraper across 50 tickers, multiple commodity contracts, regional exchange sites |
| **API Discovery** | Detect and use underlying REST/GraphQL APIs instead of scraping HTML. Reverse-engineer network requests. | Setup only | SPAs backed by JSON APIs, data portals with hidden endpoints |
| **Agentic Navigation** | Full orchestrator → sub-agent pipeline. Natural language prompt, LLM-driven task decomposition, multi-step browser interactions. | Setup + occasional re-planning | Login-gated portals, complex multi-step forms, sites requiring search + filter + extract flows |

**Auto-detection:** During pipeline setup, the system analyzes the target URL and recommends the simplest sufficient mode. The user can override. This is both a UX win (faster, simpler for easy cases) and a cost win (no LLM spend on trivial extractions). The first four modes cover ~70% of trading alt-data sources. Agentic mode is the fallback for everything else.

**API Discovery mode** is unique to Forum's trading vertical. Many financial data sources (exchanges, government portals, data aggregators) serve their web pages from underlying REST APIs. Detecting and using these APIs directly is faster, more reliable, and cheaper than browser-based scraping. The Search Agent checks for: `llms.txt`, `sitemap.xml`, XHR/fetch requests in the browser's network tab, OpenAPI/Swagger endpoints, and GraphQL introspection. If a clean API is found, the extraction code targets the API directly — no Playwright, no headless browser, no proxy costs.

### 5.5 Pipeline Variables & Parameterization

Pipelines support reusable variables that can be referenced in URLs, navigation prompts, and extraction logic. Variables are defined at the pipeline level and can be overridden per-run via API.

**Syntax:** `@variableName` in prompts and URL templates.

**Variable types:**

| Type | Description | Storage |
|------|-------------|---------|
| **String** | Plain text values (tickers, search terms, dates) | Pipeline config (Postgres) |
| **List** | Array of values to iterate over (ticker watchlist, ZIP codes, contract names) | Pipeline config (Postgres) |
| **Secret** | Passwords, API keys, session tokens. Never logged, never sent to LLMs. | AWS Secrets Manager (encrypted at rest, decrypted only during execution) |

**Example:** An analyst creates one pipeline template for SEC EDGAR filings:
- URL: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%%&type=10-K`
- Variables: `tickers` (list) = `["AAPL", "MSFT", "GOOGL", "AMZN"]`
- The pipeline iterates over the list, extracting filings for each ticker.

**API override per-run:**
```json
POST /v1/pipelines/{id}/run
{
  "variables": {
    "tickers": ["TSLA", "NVDA"]
  }
}
```

This enables watchlist-style workflows where the same pipeline logic runs across many instruments without duplicating pipeline definitions.

---

## 6. Tenancy Model & Pricing

### 6.1 Decision: Tiered Hybrid with Pricing Benchmarked Against Kadoa

Kadoa's pricing: Free (500 credits, no CC), Self-Service ($39/mo, 25,000 credits), Enterprise (custom). Their credit system charges 2 credits per structured row, 1 per raw row, 10 minimum per run. At $39/mo, a typical user running ~8 daily pipelines extracting ~50 rows each is within budget. Kadoa is running shared infrastructure for self-service — there is no way they're spinning up per-customer orchestration environments at $39/mo. Forum follows a similar model but prices slightly higher to reflect the alt-data/trading vertical and richer pipeline capabilities.

### 6.2 Forum's Pricing Tiers

| Dimension | Free | Self-Service ($49-79/mo) | Enterprise Base ($500-2,000/mo) | Enterprise Dedicated ($3,000-10,000+/mo) |
|-----------|------|------------------------|-------------------------------|----------------------------------------|
| Credits | ~500 | 25,000-50,000/mo | Custom volume / unlimited with rate limits | Custom |
| Active pipelines | 3-5 | 10-20 | Unlimited | Unlimited |
| Scheduling | Daily only | Hourly minimum | Minute-level | Minute-level |
| Data delivery | Preview only (dashboard) | S3, webhook, Snowflake | All connectors | All connectors |
| Compliance | Basic (robots.txt) | Basic + source blacklist | Full engine (PII, TOS, audit trail, compliance officer role) | Full engine |
| Auth | API key | API key + Cognito | SSO/SAML, RBAC, team workspaces | SSO/SAML, RBAC, team workspaces |
| Orchestration | MWAA Serverless (shared) | MWAA Serverless (shared) | MWAA Serverless (customer VPC) | MWAA Provisioned (dedicated) |
| Compute | Shared ECS, Fargate isolation | Shared ECS, Fargate isolation | Shared ECS, Fargate isolation | Dedicated ECS cluster |
| Database | Shared RDS, schema-per-tenant | Shared RDS, schema-per-tenant | Shared RDS, per-tenant KMS | Dedicated RDS instance |
| Storage | Shared S3, prefix-per-tenant | Shared S3, prefix-per-tenant | Shared S3, IAM-enforced | Dedicated S3 bucket |
| Network | Shared VPC | Shared VPC | Shared VPC, dedicated security groups | Dedicated VPC |
| Est. cost to serve | ~$0 | $15-40/mo | $50-200/mo | $500-2,000/mo |
| Target margin | N/A (acquisition) | 50-80% | 70-90% | 60-80% |

### 6.3 Credit System

Credits are consumed on successful extraction runs, not pipeline setup. This encourages experimentation (create and test pipelines freely, pay for production execution). Credit costs per run: 2 credits per structured row extracted, 1 credit per raw data row, 10 credit minimum per run. Credits reset monthly, do not carry over. Failed extractions are not charged. Preview runs during pipeline setup are free.

**Credit cost transparency:** The dashboard displays a credit cost calculator showing estimated monthly cost based on pipeline count, schedule frequency, and average row count. Each pipeline shows its per-run credit consumption and projected monthly total. The docs publish clear credit cost tables. Transparency builds trust — analysts managing budgets need predictability.

### 6.4 Free & Self-Service Tier — Shared Infrastructure

All Free and Self-Service users share a single infrastructure pool:

- **Compute:** Shared ECS Fargate cluster. Each pipeline task runs as an isolated Fargate microVM (Firecracker). Per-workflow IAM execution roles enforced by MWAA Serverless — each workflow can only access its tenant's S3 prefix, Secrets Manager path, and RDS schema. This is infrastructure-level isolation, not application-level.
- **Database:** Schema-per-tenant in PostgreSQL. Application middleware sets `search_path` to tenant schema on every connection. Row-level security as defense-in-depth.
- **Storage:** S3 prefix-per-tenant with IAM policies restricting access. Per-tenant KMS encryption keys means data is cryptographically isolated even at rest.
- **Orchestration:** MWAA Serverless. Each workflow gets its own IAM execution role. No shared Airflow workers — each task runs in its own Fargate container. Zero idle cost. No noisy-neighbor risk.
- **Why this works for finance:** Fargate microVMs provide real VM-level separation, not just container namespaces. IAM enforcement means even a buggy extraction script cannot access another tenant's data — AWS rejects the API call at the infrastructure level. Most SOC 2 audits accept this model.

### 6.5 Enterprise Tiers — Isolation as a Feature

**Enterprise Base** runs MWAA Serverless in the customer's VPC with their own IAM roles. Same Serverless architecture as Free/Self-Service, but network-isolated. Cost-effective for most enterprise customers.

**Enterprise Dedicated** gets a fully isolated environment provisioned via Terraform:

```hcl
module "tenant_environment" {
  source           = "./modules/tenant-vpc"
  tenant_id        = "acme-capital"
  tenant_tier      = "enterprise-dedicated"
  region           = "us-east-1"
  vpc_cidr         = "10.{tenant_index}.0.0/16"
  transit_gw_id    = aws_ec2_transit_gateway.main.id
  ecs_task_cpu     = 2048
  ecs_task_memory  = 4096
  browser_pool_min = 2
  browser_pool_max = 10
  rds_instance_class    = "db.r6g.large"
  rds_storage_encrypted = true
  rds_kms_key_id       = aws_kms_key.tenant_keys["acme"].arn
  mwaa_environment_class = "mw1.medium"   # Provisioned MWAA
  compliance_ruleset     = "strict"
  source_blacklist       = ["blocked-domain.com"]
  pii_detection_enabled  = true
}
```

Customer VPC connects to Management VPC via Transit Gateway. Only orchestration commands, LLM API calls, and platform updates cross this boundary. Customer data never leaves their VPC except to their own designated destinations.

### 6.6 Shared Infrastructure (Management VPC)

Always shared across all tenants regardless of tier:

- Tenant Provisioning Service (IaC automation)
- LLM Gateway (proxies to Anthropic/OpenAI, tracks token usage per tenant)
- Billing & Metering Service
- Platform API (tenant management, user management, plan enforcement)
- Monitoring Aggregation (collects CloudWatch metrics across all tenants)
- Agent Model Registry (versioned agent code, prompt templates)
- CI/CD (deploys agent code updates to all tenant environments)

### 6.7 Additional Tenancy Decisions

**Single account vs multi-account:** Start with a single AWS account. Multi-account (AWS Organizations) adds significant complexity. VPC-per-tenant within one account is strong enough for almost all compliance requirements. Offer multi-account only as a future white-glove tier.

**Regional strategy:** Start in us-east-1. Parameterize region in Terraform modules from day one so multi-region is a config change, not a rewrite.

**NAT Gateway costs:** Browser infrastructure makes heavy outbound HTTP requests. NAT data processing is $0.045/GB — can become a major line item. Use VPC endpoints for AWS service traffic. Factor NAT cost into per-pipeline pricing.

---

## 7. Pipeline Orchestration — MWAA Architecture

### 7.1 Decision: MWAA Serverless for Free/Self-Service, Provisioned for Enterprise Dedicated

The orchestration layer is tiered to match the pricing and isolation model. The key insight: MWAA Serverless and MWAA Provisioned are architecturally different products that share the Airflow conceptual model, enabling clean migration between tiers.

### 7.2 How MWAA Serverless Works (Behind the Scenes)

MWAA Serverless is, at its core, an EventBridge Scheduler + ECS Fargate task launcher + Airflow dependency graph evaluator, wrapped in a managed service. There are no persistent workers, schedulers, or web servers. The execution model:

1. EventBridge Scheduler (used internally by MWAA Serverless) fires the cron trigger
2. MWAA Serverless reads the YAML workflow definition and evaluates the task dependency graph
3. For each task ready to run, it provisions an isolated ECS Fargate container
4. The container runs the operator logic using the workflow's dedicated IAM execution role
5. The container communicates back to the Airflow cluster via the Airflow 3 Task API
6. Resources are automatically released when the task completes
7. MWAA Serverless evaluates what tasks to run next (based on dependency graph) and repeats

**Billing model — what's included and what's not:** The $0.08/hr "AWS Managed Tasks" rate covers the Fargate containers that MWAA Serverless provisions to run each task's operator code. This is an all-in price — you don't see a separate ECS Fargate bill for these MWAA-managed containers. Every task in your workflow (whether it's `S3ListOperator`, `SnsPublishOperator`, or `EcsRunTaskOperator`) runs in its own MWAA-managed Fargate container billed at this rate.

However, when using `EcsRunTaskOperator`, the MWAA-managed container launches a *separate* ECS Fargate task — your own container with your own image, packages, and resource allocation. That second container is billed under standard ECS Fargate pricing, not under MWAA's rate. The MWAA container running the operator logic (which submits the ECS API call and polls for completion) costs ~$0.08/hr for however long it runs. The Forum extraction container it launches (running Playwright, needing 2GB+ RAM and Chromium) costs standard Fargate rates.

**Why `EcsRunTaskOperator` is required for extraction tasks (can't we just use the MWAA container directly?):** No. The MWAA-managed Fargate container is AWS's container, not yours. You have zero control over the image, installed packages, memory/CPU allocation, or any aspect of its runtime environment. AWS provisions it with their Airflow runtime image (Python + Airflow + boto3), it executes the operator code, and it terminates. You cannot SSH into it, install additional packages, or customize it in any way — the same constraint as Lambda's execution environment. This is exactly why MWAA Serverless restricts operators to the Amazon Provider Package: those operators only make AWS API calls (S3, SNS, ECS, Lambda, etc.), which is all the managed container needs the Airflow runtime and boto3 to do. Forum's extraction tasks require Playwright, a headless Chromium browser (~400MB), custom Python packages (BeautifulSoup, pandas, lxml, etc.), 1-2GB+ RAM for browser rendering of complex SPAs, and tenant-scoped IAM task roles for credential isolation. None of this can be configured on the MWAA-managed container. The `EcsRunTaskOperator` is the bridge: the MWAA container (AWS's image, AWS's environment) makes an ECS RunTask API call to launch Forum's extraction container (your Docker image with Playwright + Chromium pre-installed, your resource allocation, your IAM task role), then polls for completion. Two containers, two billing streams — but there is no alternative within MWAA Serverless. This two-container model is the intended architecture: MWAA Serverless handles scheduling and dependency resolution, while your custom containers handle the actual compute workload.

**Net cost per pipeline run:**

- Orchestration overhead (MWAA-managed containers): 4 tasks × ~30-60 seconds each at $0.08/hr ≈ $0.003-0.005 per pipeline run
- Heavy compute (Forum's extraction/load containers via EcsRunTaskOperator): ~2 tasks × 2 min each on 0.5 vCPU / 1GB ≈ $0.02-0.04 per pipeline run
- Lightweight tasks (SNS, Lambda invocations — operator runs entirely in the MWAA container): only the $0.08/hr MWAA rate applies, no separate bill
- **Total per pipeline run: ~$0.02-0.05**, dominated by the ECS Fargate compute for extraction containers

**Smart operator selection for cost optimization:** Not every pipeline step needs a separate ECS container. The DAG can mix heavy and lightweight operators:

```yaml
tasks:
  extract:
    operator: EcsRunTaskOperator         # Heavy — separate Fargate container with Playwright, 2GB RAM, tenant IAM
  transform:
    operator: LambdaInvokeFunctionOperator  # Light — MWAA container calls Lambda directly, faster cold start
  load:
    operator: EcsRunTaskOperator         # Heavy — separate container with Snowflake connector, tenant credentials
  notify:
    operator: SnsPublishOperator         # Trivial — MWAA container sends SNS API call directly, no extra compute
```

Extract and load need their own containers (heavy compute, tenant-scoped IAM, specific dependencies). Transform could be a Lambda invocation (cheaper for lightweight data transforms). Notify is just an SNS API call the MWAA orchestrator handles directly with no separate compute.

**Per-tenant IAM role assignment:** Each workflow is created with a `--role-arn` parameter that specifies which IAM execution role the workflow's tasks assume. Forum's platform assigns tenant-specific roles at workflow creation time:

```bash
# Forum's DAG generation service calls this when a user creates a pipeline:
aws mwaa-serverless create-workflow \
  --name tenant_acme__pip_cme_settlements \
  --definition-s3-location '{"Bucket": "forum-dags", "ObjectKey": "yaml/tenant_acme__pip_cme_settlements.yaml"}' \
  --role-arn arn:aws:iam::111122223333:role/forum-tenant-acme-role \
  --region us-east-1
```

The `forum-tenant-acme-role` IAM policy restricts access to only Tenant A's resources:

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::forum-data/tenants/acme/*"
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:forum/acme/*"
    },
    {
      "Effect": "Allow",
      "Action": ["ecs:RunTask"],
      "Resource": "arn:aws:ecs:us-east-1:*:task-definition/forum-pipeline-runner"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    }
  ]
}
```

This is infrastructure-level isolation enforced by AWS IAM — even a buggy or malicious extraction script in Tenant A's workflow cannot access Tenant B's S3 prefix or Secrets Manager path because AWS will reject the API call. No application-level isolation code needed.

**Workflow versioning (built-in):** MWAA Serverless automatically versions every workflow. Each `update-workflow` call creates a new immutable version while preserving previous versions. Versions are identified by alphanumeric ID and can be rolled back to. This provides free audit trail for orchestration definitions — complementing Forum's extraction code versioning in S3.

**VPC is optional:** For Free/Self-Service tiers, workflows can run on a service-managed VPC (simplifies setup). For Enterprise Base, specify the customer's VPC for network isolation.

**Monitoring is CloudWatch-native:** Task logs go to `/aws/mwaa-serverless/<workflow_id>/` in CloudWatch. Workflow and task status are queryable via `list-workflow-runs`, `list-task-instances`, and `get-task-instance` API calls. Forum's monitoring dashboard polls these APIs to present pipeline health in the UI. No custom log collection pipeline needed.

**Management API:** Creating, updating, starting, listing, and monitoring workflows is fully CLI/SDK-driven (`aws mwaa-serverless create-workflow`, `update-workflow`, `start-workflow-run`, etc.). This maps directly to Forum's architecture — the platform API calls these programmatically when users create or modify pipelines. No manual console interaction.

**Operator limitation:** Serverless only supports operators from the Amazon Provider Package (~80+ operators). This means no `PythonOperator`, no `BashOperator`, no third-party operators (Snowflake, Slack, HTTP). The reason is physical: since there are no persistent workers, there's no machine for `PythonOperator` to execute on. To run custom code, you invoke AWS services — `EcsRunTaskOperator` for heavy compute (Playwright extraction containers), `LambdaInvokeFunctionOperator` for lightweight Python functions, `BatchOperator` for batch jobs.

**Why the operator limitation doesn't matter for Forum:** Forum's pipeline logic runs in ECS Fargate containers or Lambda regardless. The only operators Forum needs are all supported: `EcsRunTaskOperator` (extraction/transform/load), `LambdaInvokeFunctionOperator` (lightweight transforms, webhook delivery), `S3KeySensor` (event-driven pipelines), `SnsPublishOperator` (notifications), `S3CreateObjectOperator` / `S3ListOperator` (S3 operations). Third-party integrations (Snowflake, Slack) are handled inside the ECS containers or Lambda functions, not at the operator level.

**Workflow definitions:** YAML-based using the open-source DAG Factory format. Simpler to generate programmatically than Python DAGs. Jinja2 templating supported for dynamic configuration.

**Cost model:** $0.08/hr per task, billed per second (1 minute minimum). Zero idle cost when no workflows are running.

**Migration path:** AWS provides the `python-to-yaml-dag-converter-mwaa-serverless` tool (available on PyPI) to convert Python DAGs to YAML, and supports bulk conversion of entire MWAA Provisioned environments to Serverless. This confirms the Serverless ↔ Provisioned migration path is a first-class supported workflow.

### 7.3 How MWAA Provisioned Works (Behind the Scenes)

MWAA Provisioned is a real Airflow cluster that AWS manages. When you create an environment:

1. AWS provisions and runs 24/7: a scheduler (parses DAGs, schedules tasks), a web server (serves the Airflow UI), and at least one worker (executes tasks)
2. These are actual servers (EC2/Fargate-backed) with CPU, memory, disk, and network access
3. Workers run your task code directly — `PythonOperator` tasks execute Python inside the worker process
4. Additional workers auto-scale based on task queue depth

**Full operator access:** All Airflow operators including `PythonOperator`, `BashOperator`, `HttpOperator`, `EmailOperator`, third-party providers (Snowflake, Slack, etc.), and any custom operators.

**Airflow web UI:** Full access to the DAG monitoring interface, manual DAG triggers, task log viewing, and task clearing for re-runs.

**Cross-pipeline orchestration:** Native support for inter-DAG dependencies via `ExternalTaskSensor` and dataset-aware scheduling (Airflow 3). Example: "Don't run the portfolio risk pipeline until both the CME settlements pipeline and the FRED rates pipeline have completed today." This is a significant Enterprise capability.

**Workflow definitions:** Python DAG files uploaded to S3.

**Cost model:** Always-on. Small: $0.49/hr (~$365/mo minimum). Medium: $0.74/hr (~$551/mo). Large: $0.99/hr (~$737/mo). Plus additional workers, schedulers, web servers, and storage.

### 7.4 MWAA Cost Comparison (us-east-1)

Assumptions per user: 8 pipelines/day, 4 tasks each, ~1 min of MWAA orchestration overhead per task (submitting ECS API call + polling).

**Note:** These figures represent only the MWAA orchestration cost (the managed containers running operator code), not the ECS Fargate compute for Forum's extraction/load containers. ECS Fargate costs are identical regardless of orchestrator choice and add roughly $0.02-0.04 per pipeline run on top. For MWAA Provisioned, the environment runs the operator code directly on its workers (no separate ECS tasks needed for PythonOperator), so compute is bundled into the environment cost.

| Users | MWAA Serverless (orchestration only) | MWAA Provisioned (Small, all-in) | Ratio |
|-------|--------------------------------------|----------------------------------|-------|
| 10 | ~$26/mo + ~$50-100 ECS | ~$379/mo | ~2-5x |
| 50 | ~$128/mo + ~$250-500 ECS | ~$654/mo | ~1.5-3x |
| 200 | ~$512/mo + ~$1,000-2,000 ECS | ~$1,725/mo | ~1-1.5x |
| 500 | ~$1,280/mo + ~$2,500-5,000 ECS | ~$4,500/mo | ~1-1.2x |

The cost gap narrows when accounting for ECS compute, but Serverless still wins at lower scale due to zero idle cost. At higher user counts (200+), the total costs converge. However, Serverless retains the key advantage of per-workflow IAM isolation without any custom multi-tenancy code, which is worth the cost parity. The provisioned environment at 200+ users would require building application-level tenant isolation on shared workers.

The crossover point where Provisioned becomes genuinely cheaper (including the multi-tenancy engineering cost) is likely well beyond 500 users — at which point Forum would be generating enough revenue to absorb either cost model.

### 7.5 Why Serverless for Free/Self-Service (Not Provisioned)

A shared MWAA Provisioned environment was considered (all Free/Self-Service users on one environment). Rejected because:

- **Cost floor:** $365/mo minimum even with 1 user, vs. $0 idle cost with Serverless
- **Multi-tenancy is hard in Airflow:** Airflow Connections are global to the environment (no per-DAG credential scoping). All tasks on a shared worker share the same IAM role, filesystem, and process space. A bug or malicious script in one tenant's extraction code could access another tenant's credentials or data. You'd have to build application-level isolation on top of Airflow, which is fragile.
- **Serverless gives you tenant isolation for free:** Per-workflow IAM roles and per-task Fargate containers mean tenants are isolated at the infrastructure level without any custom code.
- **Noisy neighbors:** One user's misbehaving DAG on a shared Provisioned worker can starve other users' tasks of CPU/memory. Serverless tasks each get their own compute.

### 7.6 Why Provisioned for Enterprise Dedicated

Enterprise Dedicated customers get their own MWAA Provisioned environment because:

- **No multi-tenancy concern:** It's their environment, their workers, their data. Running extraction code directly on workers via `PythonOperator` is perfectly secure.
- **Predictable execution:** No cold-start latency. Workers are always running, tasks execute immediately.
- **Full operator access:** `PythonOperator` for direct code execution, `HttpOperator` for API calls, `EmailOperator` for SMTP notifications, third-party providers (SnowflakeOperator, SlackWebhookOperator), and custom operators if the customer's data engineering team wants to extend Forum's orchestration.
- **Cross-pipeline dependencies:** Native Airflow support for inter-DAG coordination via `ExternalTaskSensor` and dataset-aware scheduling. Critical for funds running 50+ interconnected pipelines feeding a unified analytics layer.
- **Airflow web UI:** Teams with existing Airflow expertise can interact with DAGs directly, inspect task logs, manually trigger runs, and clear failures.

### 7.7 DAG Structure: Two Layers, One Pipeline

Pipeline logic (extraction code, transforms, load scripts) and orchestration definitions (DAGs) are deliberately separated:

```
S3: forum-data/tenants/acme/
  └── pipelines/
      ├── pip_cme_settlements/
      │   ├── code/
      │   │   ├── v1/extract.py        ← Agent-generated Playwright extraction logic
      │   │   ├── v2/extract.py        ← Updated after self-healing
      │   │   └── latest → v2
      │   ├── transforms/
      │   │   └── transform.py         ← Type casting, normalization rules
      │   ├── schema/
      │   │   ├── v1.json
      │   │   └── v2.json
      │   └── config.json              ← Schedule, destination, notifications, metadata
```

Orchestration definitions are auto-generated from pipeline config and are thin wrappers:

**Serverless (YAML, for Free/Self-Service/Enterprise Base):**
```yaml
tenant_acme__pip_cme_settlements:
  dag_id: tenant_acme__pip_cme_settlements
  schedule: "0 18 * * 1-5"
  start_date: "2025-01-01"
  catchup: false
  tags: ["tenant:acme", "category:commodities"]
  tasks:
    extract:
      operator: airflow.providers.amazon.aws.operators.ecs.EcsRunTaskOperator
      cluster: forum-shared-cluster
      task_definition: forum-pipeline-runner
      overrides:
        containerOverrides:
          - name: runner
            command: ["python", "run_extraction.py"]
            environment:
              - { name: TENANT_ID, value: acme }
              - { name: PIPELINE_ID, value: pip_cme_settlements }
              - { name: STAGE, value: extract }
              - { name: CODE_VERSION, value: latest }
      dependencies: []
    transform:
      operator: airflow.providers.amazon.aws.operators.lambda_function.LambdaInvokeFunctionOperator
      function_name: forum-transform-runner
      payload: '{"tenant": "acme", "pipeline": "pip_cme_settlements"}'
      dependencies: [extract]
    load:
      operator: airflow.providers.amazon.aws.operators.ecs.EcsRunTaskOperator
      cluster: forum-shared-cluster
      task_definition: forum-pipeline-runner
      overrides:
        containerOverrides:
          - name: runner
            command: ["python", "run_extraction.py"]
            environment:
              - { name: TENANT_ID, value: acme }
              - { name: PIPELINE_ID, value: pip_cme_settlements }
              - { name: STAGE, value: load }
      dependencies: [transform]
    notify:
      operator: airflow.providers.amazon.aws.operators.sns.SnsPublishOperator
      target_arn: "arn:aws:sns:us-east-1:111122223333:forum-pipeline-notifications"
      message: "Pipeline pip_cme_settlements completed for tenant acme"
      dependencies: [load]
```

Note the mixed operator strategy: extract and load use `EcsRunTaskOperator` (heavy compute — Playwright browsers, Snowflake connectors, tenant-scoped IAM credentials). Transform uses `LambdaInvokeFunctionOperator` (lightweight data transforms — cheaper, faster cold start). Notify uses `SnsPublishOperator` (trivial API call — the MWAA orchestrator container handles it directly with no additional compute).

**Provisioned (Python, for Enterprise Dedicated):**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from forum.runner import run_pipeline_stage

with DAG(
    dag_id="tenant_acme__pip_cme_settlements",
    schedule="0 18 * * 1-5",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["tenant:acme", "category:commodities"],
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=run_pipeline_stage,
        op_kwargs={"tenant": "acme", "pipeline": "pip_cme_settlements", "stage": "extract"},
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=run_pipeline_stage,
        op_kwargs={"tenant": "acme", "pipeline": "pip_cme_settlements", "stage": "transform"},
    )
    load = PythonOperator(
        task_id="load",
        python_callable=run_pipeline_stage,
        op_kwargs={"tenant": "acme", "pipeline": "pip_cme_settlements", "stage": "load"},
    )
    extract >> transform >> load
```

The `run_pipeline_stage` function does the same thing as the ECS container: pulls extraction code from S3, pulls credentials from Secrets Manager, executes, writes results. The difference is where it runs — on the worker directly (Provisioned) vs. in a Fargate container (Serverless).

**Migration between tiers** is a metadata operation: regenerate the orchestration wrapper (YAML → Python or vice versa), repoint storage and credential paths. The pipeline logic, extraction code, and transforms are unchanged. AWS provides the `python-to-yaml-dag-converter-mwaa-serverless` library (available on PyPI) for automated conversion, and supports bulk migration of entire MWAA Provisioned environments to Serverless in a single operation. The reverse direction (Serverless YAML → Provisioned Python) is straightforward template generation since the concepts map one-to-one — both are Airflow under the hood. For Enterprise upgrades, the process is: convert YAML workflows to Python DAGs, upload to the dedicated environment's S3 DAGs bucket, update the workflow's IAM role to the customer's dedicated role. Automated in Forum's provisioning service.

### 7.8 Audit, Versioning, and Backfill — Application Layer, Not Orchestrator

None of the following comes from MWAA (either version). These are application-layer systems that Forum builds regardless of orchestrator choice:

- **Extraction code versioning:** Every agent-generated script stored as a versioned artifact in S3. Pipeline metadata tracks which version is active. Each run record references the code version executed.
- **Pipeline configuration audit log:** Append-only table recording every change: who, what, when, old value, new value. Immutable storage (S3 Object Lock).
- **Run history with traceability:** Each run links to: trigger type, code version, schema version, input parameters, row count, data location, duration, compliance checks.
- **Backfill:** Custom application logic, not Airflow's backfill feature. Forum's backfill means "go to the source and fetch historical data" — navigating archive pages, iterating date ranges, hitting APIs with historical parameters. The agents determine how to access historical data. The orchestrator just runs N parameterized tasks with concurrency control (Step Functions Map state or MWAA task fan-out). Airflow's built-in backfill (re-trigger DAG for past execution dates) doesn't map to this use case.

---

## 8. LLM Cost Architecture

### 8.1 LLM Gateway Pattern

Do not give customers direct LLM API keys. Build a centralized LLM Gateway in the Management VPC that all agent sub-tasks call through. This gateway handles:

1. **Authentication** — internal service auth from ECS tasks
2. **Budget enforcement** — monthly token limit per tenant tier
3. **Model routing** — selects model based on agent type
4. **Semantic caching** — deduplicates similar page analyses across tenants
5. **Logging** — tenant_id, pipeline_id, agent_type, model, tokens, cost, latency
6. **Usage tracking** — real-time counter per tenant for billing

### 8.2 Model Routing Per Agent Type

| Agent / Task | Model | Rationale | Est. Cost Per Call |
|-------------|-------|-----------|-------------------|
| Page structure analysis | Claude Haiku 4.5 | Pattern matching, not deep reasoning | ~$0.001-0.01 |
| Schema inference | Claude Sonnet 4.5 | Data semantics, column naming, type inference | ~$0.01-0.05 |
| Navigation code gen | Claude Sonnet 4.5 | Code quality + web interaction patterns | ~$0.02-0.10 |
| Extraction code gen | Claude Sonnet 4.5 | Correct CSS/XPath selectors from HTML analysis | ~$0.02-0.10 |
| TOS analysis, complex reasoning | Claude Opus 4.5 | Nuanced judgment, legal text understanding | ~$0.10-0.50 |
| Self-healing (re-analyze page) | Claude Sonnet 4.5 | Same as extraction code gen with diff context | ~$0.02-0.10 |
| Change detection (DOM diff) | Claude Haiku 4.5 | Structural hash comparison, change classification | ~$0.001-0.01 |
| PII detection | Haiku or Presidio | Pattern matching + NER. Presidio is free for most cases | ~$0.001 or $0 |
| Data quality analysis | Claude Haiku 4.5 | Statistical anomaly description | ~$0.001-0.01 |

### 8.3 Cost Per Pipeline

**Setup (one-time, LLM-heavy):** ~$0.30-0.50 per pipeline. Page analysis (Haiku × 2-3): ~$0.02. Schema inference (Sonnet × 1): ~$0.03. Navigation code gen (Sonnet × 1-3): ~$0.15. Extraction code gen (Sonnet × 2-5): ~$0.25. Validation (Haiku × 2): ~$0.02.

**Execution (recurring, LLM-free):** $0 in LLM costs. Generated code runs as Playwright scripts. Only costs are ECS compute (~$0.01-0.05/run), S3 storage (negligible), proxy egress.

**Self-healing (triggered, LLM-moderate):** ~$0.15-0.20 per healing event. Expected frequency: ~1/month per pipeline depending on source volatility.

### 8.4 Semantic Caching

Many websites share templates (Shopify, WordPress, government CMS). Hash the page's structural signature (tag hierarchy, class patterns — not content). Check if a previous analysis exists for a structurally similar page. If yes, return cached extraction template and only re-run schema mapping. Store in Redis with structural hash as key, extraction code skeleton as value.

### 8.5 Budget Enforcement

Per-tenant monthly token budgets enforced in real-time by the LLM Gateway. Standard tier: ~1M tokens/month (~50-100 pipeline setups + healing). Enterprise: 10M+. Pipeline creation pauses if budget exceeded, tenant notified.

### 8.6 Response Caching (Proxy-Level)

Raw page responses are cached to avoid redundant requests to the same source. This reduces cost (fewer proxy requests), latency, and detection risk (fewer requests to the target site). Caching operates at two levels with strict tenant isolation.

**Level 1 — Intra-Tenant Response Cache (Phase 1):**

If a single tenant has multiple pipelines targeting the same source URL, or the same pipeline is triggered multiple times within a short window, cache the raw page response and share it across that tenant's pipelines.

Cache key: `{tenant_id}:{url}:{proxy_region}:{timestamp_bucket}`

Timestamp bucket is configurable per-pipeline (e.g., 5-minute windows for fast-changing sources, 1-hour windows for stable sources). A hedge fund running 10 pipelines against CME's settlement page at the same daily schedule hits CME once, not 10 times.

Storage: Redis (tenant-namespaced keys) for hot cache (recent responses <5MB), S3 tenant prefix for cold storage (larger responses, longer TTL). Cache entries are encrypted at rest with the tenant's KMS key.

**Level 2 — Cross-Tenant Structural Cache (Phase 2+):**

This extends the semantic caching from §8.4. Two different tenants scraping the same Shopify product page template benefit from shared *structural analysis* (extraction template, selector patterns, code skeleton) — but never share *page content or extracted data*.

Cache stores only: page structural signature (tag hierarchy, class patterns, template fingerprint) → extraction code skeleton. No content, no data, no tenant-specific information. This is safe because the structural signature is a property of the website template, not of any tenant's data.

**Privacy boundary (strictly enforced):**
- **Never cached cross-tenant:** raw page responses, extracted data, authentication cookies, session state, pipeline configuration, target URLs
- **Cached cross-tenant (structural only):** page template signatures → extraction code skeletons, DOM structure patterns → selector recommendations

**Architecture:**

```
Pipeline Runner → Browser Module → Cache Check
                                    ├── [hit: tenant-scoped response cache] → return cached response
                                    └── [miss] → Proxy → Fetch → Store in tenant cache → Return
```

The cache layer lives in `packages/browser/cache.py` and sits between the browser module and the proxy layer. The pipeline runner is unaware of caching — it just requests a page and gets a response.

---

## 9. Schema Versioning System

### 9.1 Two Distinct Schema Concerns

**Platform schema:** Internal database tables (pipelines, extraction_runs, compliance_rules). Standard SaaS migration problem. Use Alembic or Flyway. Iterate migrations across all tenant schemas.

**Extraction schema:** The shape of each pipeline's extracted data. This is the unique, important problem. Columns, types, constraints that downstream consumers (Snowflake tables, trading models) depend on.

### 9.2 Extraction Schema Registry

```sql
CREATE TABLE extraction_schemas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
  version         INTEGER NOT NULL,
  schema_def      JSONB NOT NULL,
  parent_version  INTEGER,
  change_type     TEXT NOT NULL,    -- 'initial', 'user_edit', 'auto_heal', 'source_change'
  change_summary  TEXT,
  breaking        BOOLEAN NOT NULL DEFAULT FALSE,
  created_by      TEXT NOT NULL,    -- 'user:analyst@fund.com' or 'system:self-heal'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted_at     TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'draft'  -- 'draft', 'active', 'retired'
);
```

Schema definition stored as JSONB:
```json
{
  "columns": [
    {"name": "contract", "type": "string", "nullable": false},
    {"name": "settlement_price", "type": "float", "nullable": false, "constraints": {"min": 0}},
    {"name": "volume", "type": "integer", "nullable": true},
    {"name": "last_updated", "type": "datetime", "nullable": false}
  ],
  "primary_key": ["contract", "last_updated"],
  "dedup_key": ["contract", "last_updated"]
}
```

### 9.3 Breaking vs Non-Breaking Changes

| Change Type | Breaking? | Auto-Promote? |
|------------|-----------|---------------|
| Add nullable column | No | Yes |
| Add non-nullable column | Yes | No — requires approval |
| Remove column | Yes | No — requires approval |
| Rename column | Yes | No — requires approval |
| Change column type | Yes | No — requires approval |
| Widen constraints | No | Yes |
| Narrow constraints | Yes | No |
| Reorder columns | No | Yes |

### 9.4 Downstream Notification

When a schema version is promoted, emit an event via SNS/webhook:

```json
{
  "event": "schema.version.promoted",
  "pipeline_id": "pip_abc123",
  "pipeline_name": "CME Settlements",
  "previous_version": 3,
  "new_version": 4,
  "breaking": true,
  "change_summary": "Column 'open_interest' type changed from string to integer",
  "changes": [{"type": "column_type_change", "column": "open_interest", "old_type": "string", "new_type": "integer"}],
  "promoted_by": "system:self-heal",
  "promoted_at": "2025-03-15T14:30:00Z"
}
```

### 9.5 Code ↔ Schema Binding

Every extraction code artifact is bound to a specific schema version. Every extraction run record references both code version and schema version. This enables full auditability: "What schema was in effect when this data was extracted?"

### 9.6 Shared Schema Templates

Schemas can be defined at the workspace level and reused across multiple pipelines. A "CME Settlement Schema v2" template can be referenced by any pipeline targeting CME data. When a template is updated, all referencing pipelines receive the change — subject to the same breaking change gates (§9.3). Auto-promote for non-breaking changes, approval required for breaking changes.

**SDK builder API for schemas:**
```python
from forum import SchemaBuilder

schema = (SchemaBuilder("CME Settlement")
  .field("contract", "Contract symbol", "STRING", nullable=False, example="CLZ25")
  .field("settlement_price", "Daily settlement price", "FLOAT", nullable=False, constraints={"min": 0})
  .field("volume", "Contracts traded", "INTEGER", nullable=True)
  .field("open_interest", "Open interest", "INTEGER", nullable=True)
  .field("last_updated", "Settlement date", "DATETIME", nullable=False)
  .primary_key(["contract", "last_updated"])
  .build())

# Create as reusable template
client.schemas.create_template(schema, name="CME Settlement Schema")

# Reference in a pipeline
client.pipelines.create(url="...", schema_template="CME Settlement Schema")
```

---

## 10. Auth & Secrets Strategy

### 10.1 Platform Auth (Users → Forum)

Amazon Cognito for user identity with per-tenant user pools. Support SSO/SAML for enterprise clients (hedge funds typically require Okta/Azure AD integration).

**RBAC roles per tenant:**
- **Admin:** manage users, billing, settings
- **Analyst:** create/edit/view pipelines, view data
- **Compliance Officer:** approve pipelines, view audit logs, configure compliance rules (cannot create pipelines)
- **Viewer:** read-only access to dashboards and data

### 10.2 Target Source Auth (Pipelines → Websites/APIs)

AWS Secrets Manager as the credential vault. Each tenant gets a namespace:

```
forum/{tenant_id}/sources/{source_id}/credentials
```

Credential types supported: basic auth (username/password), API keys, OAuth2 (client_id, client_secret, refresh_token), session cookies (with login flow reference).

**IAM enforcement:** ECS Fargate task roles restrict Secrets Manager access to the tenant's path only:

```json
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:forum/acme-capital/*"
}
```

### 10.3 Key Design Principle: Orchestrator Never Sees Credentials

In the Serverless tier, the MWAA orchestrator container runs with the workflow's execution role, which has permission to trigger ECS tasks but does NOT have permission to read Secrets Manager values. Only the ECS extraction/load containers (running with their own task roles) can access tenant credentials. In the Provisioned tier, workers execute pipeline code directly, so they do access Secrets Manager — but since each Enterprise customer has their own dedicated environment, this is their own credential scope. Credentials exist only in memory for the duration of execution, never persisted to disk or logs.

### 10.4 Auth Pattern Handling

- **API key / Bearer token:** Stored in Secrets Manager, injected as header. No browser needed.
- **Username/password login:** Navigation Agent generates login script during setup. Session cookies cached in Redis (encrypted, tenant-scoped) to avoid logging in every run.
- **OAuth2:** Store client credentials + refresh token. Pipeline refreshes access token before each run.
- **2FA / MFA:** TOTP-based — store seed in Secrets Manager, generate codes programmatically. SMS/email-based — pipeline pauses, user completes via Forum UI (stretch goal, not MVP).

### 10.5 Credential Lifecycle

- Detect auth failures during extraction (403, redirect to login, "session expired"). Alert user to update credentials.
- Support Secrets Manager rotation for destination credentials (Snowflake, etc.).
- Store credentials at the source level, not pipeline level. Multiple pipelines can reference the same source.

---

## 11. Compliance Engine

### 11.1 Rule Evaluation Pipeline

Every pipeline action passes through the Compliance Engine before execution. Rules evaluated in order of severity: hard blocks → soft blocks requiring approval → warnings.

### 11.2 Rule Types

| Rule | Description | Implementation |
|------|------------|----------------|
| **Source Blacklist** | Per-tenant configurable list of blocked domains/URL patterns. Checked at creation AND runtime. | Domain/regex matching. Stored in tenant config DB. |
| **robots.txt** | Fetch and parse robots.txt. Respect Crawl-delay, Disallow paths, User-agent. | robots.txt parser library. Cache per domain. Allow override with compliance officer approval. |
| **TOS Scanner** | LLM analyzes target site's Terms of Service for data collection restrictions. | LLM-based analysis at pipeline creation. Flag ambiguous TOS for human review. Re-check periodically. |
| **CAPTCHA Block** | If CAPTCHA encountered, pipeline MUST NOT attempt to solve or bypass. | Detect CAPTCHA elements in DOM. Halt immediately. Alert user. Log for audit. |
| **PII Detection** | Scan extracted data for names, emails, phone numbers, SSNs, addresses. Configurable: redact, flag, or block. | Regex patterns + NER (AWS Comprehend or Presidio). Post-extraction transform step. |
| **Rate Limiting** | Configurable delays between requests. Respect Crawl-delay. Never overwhelm target servers. | Token bucket rate limiter per domain. Default 1 req/sec. Back off on slow responses. |

### 11.3 Compliance Officer Role

- Distinct role with access to audit logs, pipeline approval queues, rule configuration
- Configurable as mandatory approver (every pipeline) or exception-based (only flagged pipelines)
- Mandatory compliance training for new users before pipeline creation

### 11.4 Audit Trail

Every pipeline action logged: timestamp, actor (user or agent), action taken, data accessed, compliance check results. Logs are immutable (append-only S3 with Object Lock). Exportable for regulatory review.

### 11.5 Compliance UI

Pipeline creation UI displays: persistent compliance banner showing active ruleset, real-time warnings as rules trigger, red/yellow/green status per compliance dimension, summary scorecard before pipeline activation.

---

## 12. Self-Healing & Monitoring

### 12.1 Three-Layer Monitoring

**Layer 1 — Availability:** Lightweight HTTP health checks every 5-15 minutes. Detect site down, page moved, domain expired, CAPTCHA wall. Retry with backoff, pause after N consecutive failures.

**Layer 2 — Structural Change Detection:** Periodically fetch target page, compare DOM structure against baseline via structural hashing. Score: minor (<0.3) → log. Moderate (0.3-0.7) → auto-regenerate code. Major (>0.7) → pause pipeline, alert user.

**Layer 3 — Data Quality:** Compare each extraction against historical baselines. Row count anomalies, schema violations, value distribution shifts, freshness violations, duplicate detection.

**Layer 3a — Source Grounding & Confidence Scoring:** Every extracted data point carries provenance metadata and a confidence score. This traces each value back to where it came from on the page and how certain the system is that the extraction is correct.

Per-field confidence scoring based on:
- **Selector specificity** — a unique `#settlement-price` ID scores higher than a positional `div:nth-child(3) > span`
- **Structural match** — does the extracted value's type, format, and position match the schema expectation? A price field returning a date string scores 0.
- **Historical consistency** — is this value within the expected range based on the rolling window of prior extractions? A settlement price that's 100x the previous value scores low.
- **Extraction method** — deterministic selector scores higher than regex fallback, which scores higher than LLM-inferred extraction.

Confidence levels: **High** (≥0.9) → load normally. **Medium** (0.6-0.9) → load but flag in dashboard + include in run warnings. **Low** (<0.6) → configurable: block (don't load), warn, or log. For trading pipelines, the default for low-confidence fields should be block — it's better to miss data than to load wrong data into a model.

Source grounding metadata stored per-run:
```json
{
  "field": "settlement_price",
  "value": 72.45,
  "confidence": 0.95,
  "source": {
    "url": "https://www.cmegroup.com/...",
    "selector": "#settlementTable tr:nth-child(3) td.price",
    "screenshot_region": "s3://forum-data/.../field_screenshots/settlement_price.png",
    "timestamp": "2025-03-15T14:30:00Z"
  }
}
```

**Layer 3c — Plausibility Checks (Silent Failure Detection):** The hardest failures aren't errors — they're silently wrong data. Bad selectors returning incomplete results, timing issues causing partial page loads, geo-specific rendering serving different content. These don't throw exceptions; they return structurally valid but semantically wrong data.

Plausibility checks compare each extraction's statistical properties against a rolling window of historical runs:

| Check | What It Catches |
|-------|----------------|
| **Row count stability** | Table that usually returns 47 rows suddenly returns 3 — page didn't fully load or pagination broke |
| **Value distribution shift** | Mean settlement price shifted by >3σ from 30-day rolling average — likely extracting from wrong column or table |
| **Cardinality change** | Contract list that usually has 25 unique values now has 2 — page likely showing a filtered/default view |
| **Type consistency** | A numeric field suddenly contains strings — selector is now pointing at a label instead of a value |
| **Null rate spike** | Fields that are normally 100% populated now show 40% nulls — partial page render or DOM restructure |
| **Format consistency** | Date field switching from `YYYY-MM-DD` to `MM/DD/YYYY` — source changed format or geo-specific rendering |

Plausibility failures generate the `PLAUSIBILITY_FAILED` warning (non-critical) or `PLAUSIBILITY_BLOCKED` error (critical, configurable). For trading pipelines, plausibility failures should default to blocking — flag the run for manual review rather than silently loading suspect data.

**Layer 3b — User-Defined Validation Rules:** Domain-specific rules configured per-pipeline by the analyst. These complement the system's automatic quality checks with business logic:

| Rule Type | Example |
|-----------|---------|
| **Range constraint** | `settlement_price > 0 AND settlement_price < 10000` |
| **Relative change** | `volume` should not decrease by more than 90% vs. previous run |
| **Referential integrity** | `contract` must be in the set of known active contracts |
| **Freshness** | `last_updated` must be within 24 hours of run time |
| **Completeness** | Row count must be within ±20% of 30-day average |
| **Business day** | `report_date` must be a business day (not weekend/holiday) |
| **Custom expression** | Any Python expression evaluated against the extracted DataFrame |

Rules are evaluated after extraction, before loading. Violations can be configured as: **block** (fail the run, don't load), **warn** (load but flag in dashboard + notify), or **log** (silent record for audit).

### 12.2 Self-Healing Flow

1. **Change Detected** — structural diff exceeds threshold, extraction code fails, or data quality check fails
2. **Code Regeneration** — Extraction Agent re-analyzes changed page, generates new extraction code targeting same schema
3. **Validation** — Compare new extraction output against last known good. Confidence score. Schema compatibility check.
4. **Promotion / Escalation** — High confidence → auto-promote. Medium → promote but alert. Low → pause, require human intervention.

### 12.3 Error Taxonomy

Formal, machine-readable error codes exposed in the API. Trading clients integrating via API need structured error handling, not just human-readable messages.

**Critical errors** (run marked `FAILED`, user notified, auto-retry on next schedule):

| Code | Description |
|------|-------------|
| `SOURCE_UNAVAILABLE` | Target URL returns 5xx, DNS failure, connection timeout |
| `ACCESS_BLOCKED` | 403, CAPTCHA wall, IP ban, geo-restriction |
| `EXTRACTION_FAILED` | Generated code crashed, selector mismatch, unexpected page structure |
| `SCHEMA_MISMATCH` | Extracted data doesn't match expected schema (wrong types, missing required columns) |
| `DELIVERY_FAILED` | Could not write to destination (Snowflake down, S3 permissions, webhook timeout) |
| `RATE_LIMITED` | Source or proxy rate limit exceeded after retries |
| `COMPLIANCE_BLOCKED` | Compliance engine rejected the run (blocked domain, PII detected, etc.) |
| `TIMEOUT` | Extraction exceeded maximum execution time |
| `PLAUSIBILITY_BLOCKED` | Statistical plausibility check failed hard threshold (e.g., row count dropped 90%, value distribution shifted >3σ) |
| `DETECTION_BLOCKED` | All stealth escalation levels exhausted — source is actively blocking automated access |

**Non-critical warnings** (run completes successfully, informational):

| Code | Description |
|------|-------------|
| `EMPTY_RESULTS` | Extraction returned 0 rows — data genuinely absent today (e.g., market holiday) |
| `PARTIAL_RESULTS` | Some pages succeeded, some failed — partial data delivered |
| `SCHEMA_DRIFT` | Minor non-breaking schema changes detected (new optional column appeared on source) |
| `STALE_DATA` | Extracted data is identical to the previous run (source hasn't updated) |
| `LOW_CONFIDENCE` | One or more extracted fields scored below confidence threshold (source grounding) |
| `PLAUSIBILITY_WARNING` | Statistical plausibility check flagged anomalies (row count shift, distribution drift) but within warn threshold |
| `DETECTION_SIGNAL` | Anti-bot detection signal encountered (throttling, soft block) — stealth level was auto-escalated |

**API response structure:**
```json
{
  "run_id": "run_abc123",
  "status": "COMPLETED",
  "errors": [],
  "warnings": [
    {
      "code": "STALE_DATA",
      "message": "Extracted data identical to previous run",
      "timestamp": "2025-03-15T14:30:00Z",
      "context": { "last_changed": "2025-03-14T18:00:00Z" }
    }
  ],
  "data": { "rows": 47, "schema_version": 3 }
}
```

### 12.4 Observability Stack

- CloudWatch Metrics for pipeline health (success rate, latency, data volume)
- X-Ray tracing for agent execution flows
- Custom UI dashboard: pipeline health grid, recent runs timeline, data freshness indicators, compliance activity, cost per pipeline

### 12.5 Change Detection Pipelines (Monitor Mode)

Change detection is a first-class pipeline type, not just a monitoring layer on extraction pipelines. A **Monitor Pipeline** watches a source for changes and emits alerts — without performing full structured extraction on every run. This is cheaper (fewer credits, no extraction compute) and is often the entire use case for trading: "alert me when this government page updates."

**Pipeline types:**

| Type | Description | Per-Run Cost |
|------|-------------|-------------|
| **Extraction Pipeline** | Full extract → transform → validate → load cycle. Produces structured data. | Standard (2 credits/row) |
| **Monitor Pipeline** | Lightweight page fetch → structural/content hash comparison → alert on change. No structured extraction. | Reduced (1 credit/check) |
| **Hybrid Pipeline** | Monitor on every run (cheap), trigger full extraction only when change is detected. | Monitor cost + extraction cost when triggered |

Monitor pipelines use lightweight HTTP requests (no Playwright, no headless browser) when possible, falling back to browser rendering only for JS-heavy SPAs. They compare against the previous snapshot using content hashing, structural DOM hashing, or user-defined change selectors (e.g., "watch only the table in `#settlement-data`").

**Trading use cases:**
- Government regulatory page updates (SEC, CFTC, Fed announcements)
- Exchange rule changes or new product listings
- Competitor website changes (new fund filings, team changes)
- Earnings release page updates (before structured data is available)

### 12.6 Conditional Notifications

Notifications can be filtered so users only receive alerts when specific conditions are met. Prevents alert fatigue on high-frequency pipelines.

**Condition types:**

| Condition | Example |
|-----------|---------|
| **Field value change** | "Notify when `settlement_price` for contract `CLZ25` changes" |
| **Threshold** | "Notify when `volume` exceeds 100,000" |
| **Percentage change** | "Notify when `price` changes by more than 2% vs. previous run" |
| **New rows** | "Notify when new rows appear (new filings, new contracts)" |
| **Removed rows** | "Notify when rows disappear (delisted instrument, removed filing)" |
| **Keyword match** | "Notify when extracted text contains 'force majeure' or 'default'" |

**Configuration (API):**
```json
POST /v1/pipelines/{id}/notifications
{
  "channel": "webhook",
  "endpoint": "https://trading-system.internal/alerts",
  "events": ["data_changed"],
  "conditions": [
    { "field": "settlement_price", "operator": "pct_change_gt", "value": 2.0 },
    { "field": "contract", "operator": "in", "value": ["CLZ25", "CLF26"] }
  ]
}
```

---

## 13. API / SDK Surface

### 13.1 REST API

```
POST   /v1/pipelines                    Create pipeline
GET    /v1/pipelines                    List pipelines
GET    /v1/pipelines/{id}               Get pipeline details
PATCH  /v1/pipelines/{id}               Update config
DELETE /v1/pipelines/{id}               Deactivate

POST   /v1/pipelines/{id}/run           Trigger immediate run
POST   /v1/pipelines/{id}/backfill      Historical backfill
GET    /v1/pipelines/{id}/runs          Run history
GET    /v1/pipelines/{id}/runs/{run_id} Run details + logs

GET    /v1/pipelines/{id}/data          Query extracted data
GET    /v1/pipelines/{id}/data/latest   Latest extraction
GET    /v1/pipelines/{id}/schema        Current schema

POST   /v1/extract                      Adhoc extraction (one-time, no pipeline created)
POST   /v1/sources/analyze              Analyze URL, return schema suggestion
POST   /v1/sources/preview              Preview extraction (free, sample data)

POST   /v1/schemas                      Create reusable schema template
GET    /v1/schemas                      List schema templates
GET    /v1/schemas/{id}                 Get schema template
PATCH  /v1/schemas/{id}                 Update schema template

POST   /v1/notifications/subscriptions  Subscribe to pipeline events (with optional conditions)
GET    /v1/notifications/subscriptions  List notification subscriptions
DELETE /v1/notifications/subscriptions/{id}  Unsubscribe

GET    /v1/compliance/rules             List active rules
GET    /v1/compliance/audit-log         Query audit trail
POST   /v1/compliance/check             Pre-check source URL

GET    /v1/pipelines/{id}/health        Health check & metrics
GET    /v1/alerts                       Active alerts
WS     /v1/ws/pipelines/{id}            Real-time pipeline status
```

### 13.2 SDKs

**Python SDK** — primary SDK for analyst workflows. OpenAPI spec → auto-generated client. Publish to PyPI as `forum-sdk`. Must be the most polished, most documented, and first to ship — Python is the primary language for trading desks. Includes WebSocket/SSE support for real-time events.

**TypeScript SDK** — for frontend and Node.js integrations. Auto-generated from same OpenAPI spec. Publish to npm as `@forum/sdk`.

**Adhoc extraction (SDK convenience method):**
```python
# One-time extraction, no pipeline created. Great for testing/exploration.
result = client.extract_once(
    url="https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.settlements.html",
    schema=schema  # optional — auto-detect if omitted
)
print(result.data)  # Immediate structured data
```

### 13.3 CLI

Thin wrapper around the Python SDK. Quant developers live in terminals.

```bash
forum auth login                                    # Authenticate
forum pipeline create --url <url> --schema <file>   # Create pipeline
forum pipeline list                                 # List pipelines
forum pipeline run <id>                             # Trigger immediate run
forum pipeline run <id> --variables '{"ticker":"AAPL"}'  # Run with variable override
forum pipeline data <id> --format csv               # Download latest data
forum pipeline data <id> --format json > output.json
forum pipeline logs <id>                            # View recent run logs
forum pipeline health <id>                          # Health check
forum extract --url <url>                           # Adhoc one-time extraction
forum monitor create --url <url> --selector "#data-table"  # Create monitor pipeline
```

### 13.4 MCP Server (Phase 4)

Model Context Protocol server enabling AI coding assistants (Claude, Cursor, etc.) to create and manage Forum pipelines via natural language. Exposes pipeline CRUD, data access, and monitoring as MCP tools.

---

## 14. Pipeline Lifecycle (End-to-End)

The runtime pipeline executes as **E-C-T-V-L-N** (Extract → Cleanse → Transform → Validate → Load → Notify):

1. **Source Input:** User provides URL + description + optional schema + optional navigation instructions + optional proxy location (geo-targeted extraction for region-restricted sources) + navigation mode (auto-detected or user-specified per §5.4)
2. **Discovery:** Search Agent fetches URL, discovers pages/endpoints, checks for APIs (llms.txt, sitemap.xml). Compliance Engine runs pre-checks.
3. **Schema Inference:** Extraction Agent proposes schema. User accepts, modifies, or provides their own.
4. **Code Generation:** Navigation Agent generates Playwright scripts. Extraction Agent generates selectors. Trial extraction, user confirms sample data.
5. **Cleansing & Transform Rules:** User defines (or AI suggests) transforms and validation rules. Compiled into deterministic functions. The UI provides a lightweight **visual pipeline step editor** where users can see and reorder stages: extract → cleanse → transform → validate → load. Not a full Airflow DAG UI, but a simplified step chain with drag-and-drop reordering. Pre-built transform actions available for common trading data operations: normalize date formats, convert currencies, calculate percentage changes, pivot/unpivot tables, merge with reference data, deduplicate rows, cast types.
6. **DAG Generation:** Orchestrator compiles into DAG: extract → cleanse → transform → validate → load → notify. User sets schedule.
7. **Data Delivery:** Pre-built connectors for S3, Snowflake, Redshift, BigQuery, PostgreSQL, REST webhook. SDK allows pull-based access.

### 14.1 Cleansing Stage (New)

Cleansing runs between extraction and transformation. It removes noise from raw extracted data before business-logic transforms operate on it. This is deterministic and rule-based — no LLM involvement at runtime.

**What cleansing strips:**
- HTML boilerplate, navigation elements, ads, and promotional content that leaked into extracted tables
- Header/footer rows in data tables (e.g., "Page 1 of 3", column group headers, summary rows)
- Footnote markers and disclaimer text embedded in data cells (e.g., "* preliminary", "† revised")
- Whitespace normalization (leading/trailing, multiple spaces, non-breaking spaces, zero-width characters)
- Encoding artifacts (HTML entities, Unicode control characters)
- Duplicate rows from pagination overlap

**Footnote/qualifier extraction:** When cleansing encounters footnote markers (*, †, ‡, etc.) in data cells, it doesn't just strip them — it extracts them into metadata fields. A cell containing "72.45*" becomes `value: 72.45, qualifiers: ["preliminary"]` if the footnote key maps `*` to "preliminary." The qualifier mapping is generated during pipeline setup (agent analyzes the page's footnote legend) and stored in the pipeline config.

Cleansing rules are generated during pipeline setup by the agent analyzing the source's structure, then compiled into deterministic functions. They run at near-zero cost on every execution.

### 14.2 Agent-Based Formatting (Optional Transform)

In addition to deterministic pre-built transforms, pipelines can optionally enable **LLM-assisted formatting** for sources with messy, inconsistent data. This handles cases where deterministic transforms fail because the input format varies unpredictably:

**Examples:**
- A source reports prices as "1,234.56" in one region and "1.234,56" in another — an LLM infers locale from context
- Column headers change from "Settlement Price" to "Sttl. Px" after a site redesign — an LLM recognizes semantic equivalence and remaps
- Mixed date formats within the same table ("March 15, 2025" and "15/03/2025") — an LLM normalizes based on context
- Merged cells in an HTML table where a category label spans multiple rows — an LLM restructures into flat rows

**Architecture:** Like all LLM-powered features, the cost model is setup-heavy, runtime-light. When the agent encounters a formatting ambiguity during setup, it generates a formatting rule and compiles it into a deterministic function. The function handles the known patterns at zero LLM cost per-run. Only when a *new* pattern appears (one the compiled rule doesn't handle) does the system invoke the LLM to generate an updated rule — which then gets compiled for subsequent runs.

Formatting rules are versioned alongside extraction code in S3. The self-healing flow applies here too: if a new format pattern appears, the system can regenerate the formatting rule automatically and validate against expected output before promoting.

---

## 15. Gaps Identified & Build Plan

### 15.1 Critical Gaps

- **LLM Cost Management** — Solved via LLM Gateway (see §8)
- **Schema Versioning & Data Contracts** — Solved via Schema Registry (see §9) and Shared Schema Templates (§9.6)
- **Multi-Page & Cross-Source Pipelines** — Pipeline composition: pipelines that depend on and join outputs from other pipelines (Phase 4)
- **Authentication & Session Management** — Solved via Secrets Manager pattern (see §10), Secret variable type (§5.5)
- **Backfill & Historical Data** — Specialized logic for date-based pagination, rate limits, resumable crawls (Phase 3)
- **Browser Extension** — Chrome extension for visual point-and-click element selection (Phase 4)
- **Data Deduplication** — Content hashing, incremental extraction, change data capture semantics
- **Tenant Onboarding Automation** — Full control plane: signup → payment → provision → configure → deploy → onboard (Phase 2)
- **Disaster Recovery** — Cross-region replication, automated backups, S3 Object Lock for audit compliance (Phase 4)
- **Navigation Mode Tiering** — Solved via tiered navigation modes (§5.4): deterministic modes for simple sources, agentic for complex
- **Pipeline Variables & Parameterization** — Solved via variables system (§5.5) for watchlist-style workflows
- **Change Detection as First-Class Feature** — Solved via Monitor Pipelines (§12.5) and Hybrid Pipelines
- **Conditional Notifications** — Solved via filtered notification conditions (§12.6)
- **Code Artifact Visibility** — Solved via code export/edit capabilities (§15.3, Phase 3+)
- **User-Defined Validation Rules** — Solved via domain-specific rule builder (§12.1 Layer 3b)

### 15.2 Phased Build Plan

The build plan follows a **free/basic-tier-first strategy**: ship the core product on MWAA Serverless with limited features, validate with early users, then expand to enterprise functionality. Each phase produces a usable, deployable product — not just a milestone toward the final vision.

| Phase | Weeks | Deliverables |
|-------|-------|-------------|
| **0 — Core Agent** | 1-6 | Extraction agent as standalone Python service. Input: URL + description. Output: extraction code + sample data. No UI, no multi-tenancy. Implement tiered navigation modes (single page, paginated list, list+detail, API discovery) — test deterministic modes without LLM. Agentic mode for complex sources. **Browser identity & anti-detection**: implement 4-layer stealth system (network, fingerprint, behavioral, session), adaptive stealth calibration (auto-detect minimum required stealth level per source). Test against 20+ diverse websites including trading-specific sources (CME, SEC EDGAR, FRED, government portals) and anti-bot-protected sites (Cloudflare, DataDome). |
| **1 — Platform MVP (Free & Basic Tier)** | 7-16 | REST API (FastAPI), PostgreSQL, S3, basic auth (API keys), pipeline CRUD with navigation mode selection, **pipeline variables & URL templates**, MWAA Serverless orchestration (YAML DAGs → ECS tasks), S3/webhook delivery, **adhoc extraction endpoint** (`POST /v1/extract`), **monitor pipelines** (change detection as first-class pipeline type), Python SDK v0.1, **CLI tool**, free preview runs (no credit cost for setup/testing), formal error taxonomy in API responses (including `PLAUSIBILITY_BLOCKED`, `DETECTION_BLOCKED`, `LOW_CONFIDENCE`), basic data explorer in dashboard, single-tenant deployment. LLM Gateway with semantic caching. Schema registry (versioning, breaking change detection). **E-C-T-V-L-N pipeline**: cleansing stage between extract and transform (boilerplate stripping, footnote extraction, whitespace normalization). **Intra-tenant response caching** (Level 1 proxy cache, Redis + S3). **Source grounding metadata** (per-field confidence scores, selector provenance). **Plausibility checks** (row count stability, distribution shift, cardinality change). **Detection signal monitoring** (throttle detection, soft block detection, auto stealth escalation). |
| **2 — UI, Self-Healing & Growth Features** | 17-24 | React web UI (pipeline builder, monitoring dashboard, data preview/explorer, one-click CSV/JSON export), change detection agent, self-healing code regeneration with validation gates, data quality monitoring (system checks + **user-defined validation rules**), **conditional notifications** (field change, threshold, percentage, keyword), notification channels (email, Slack, webhooks, WebSocket), basic compliance engine (robots.txt, source blacklist, rate limiting, **compliance-aware stealth selection** — llms.txt and robots.txt feed into stealth level), **tags/folders** for pipeline organization, **shared schema templates** (workspace-level reusable schemas), async preview with email notification when ready, **agent-based formatting** (LLM-assisted transform for ambiguous formats, compiled to deterministic rules), **cross-tenant structural cache** (Level 2 — shared extraction templates, no content sharing). Multi-tenancy foundation: schema-per-tenant, S3 prefix-per-tenant, per-workflow IAM via MWAA Serverless. Credit system, billing & metering. Cognito auth. Terraform IaC for environment management. **Persistent browser profiles** (encrypted, tenant-scoped, for session continuity across runs). |
| **3 — Enterprise & Compliance** | 25-34 | Full compliance engine (PII detection, TOS scanner, CAPTCHA blocking, compliance officer role, approval workflows, audit trail with S3 Object Lock), **downloadable compliance reports** (PDF/CSV), compliance hints in pipeline creation UI, SSO/SAML, RBAC (Admin/Analyst/Compliance Officer/Viewer), team workspaces (sub-organizational units within tenants), MWAA Provisioned for Enterprise Dedicated (Python DAGs, full operator access, Airflow UI, cross-pipeline dependencies via ExternalTaskSensor), dedicated VPC provisioning via Terraform, backfill engine (date-range iteration, resumable crawls), **code artifact visibility** (engineers can view and directly edit agent-generated extraction/transform code), IP address logging per run, **Trust Center** (public security page). **Cohort-based device profile library** (production-grade fingerprint rotation). |
| **4 — Scale & Ecosystem** | 35+ | Chrome extension (visual point-and-click element selection), multi-page pipeline composition (cross-pipeline dependencies and joins), TypeScript SDK, **MCP Server** (AI assistant integration), Google Sheets integration, GitHub Actions integration, email as data delivery channel, **LLM-as-a-judge** data quality checks, website crawling endpoint (`POST /v1/crawl` for LLM-ready markdown), SOC 2 Type II certification, DR automation (cross-region replication), performance optimization, trading-specific pipeline template library. |

### 15.3 Code Artifact Visibility (Phase 3+)

Forum's code-generation architecture produces real, auditable extraction code — not black-box LLM outputs. This is a unique asset that should be exposed to power users:

- **View generated code:** Engineers can inspect the Playwright scripts, CSS/XPath selectors, and transform functions that agents generated for any pipeline. Available in the UI and via API (`GET /v1/pipelines/{id}/code`).
- **Edit code directly:** Engineers can fork the agent-generated code and make manual edits. Edited code is versioned alongside agent-generated versions. Manual edits override agent auto-healing — the system will not regenerate code that a human has customized unless explicitly asked.
- **Code export:** Download the full pipeline code (extraction + transform + validation) as a standalone Python package that can run outside Forum. This is an escape hatch for enterprises that want to bring pipelines in-house.
- **Hybrid mode:** Agent generates the initial code, engineer refines it, agent handles maintenance (re-generating only the parts the engineer hasn't customized). Track which code sections are "agent-owned" vs. "human-owned."

---

## 16. Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph or custom Python state machine |
| Browser Automation | Playwright (multi-browser: Chromium, patched Chromium w/ TLS spoofing, Camoufox/Firefox) |
| Anti-Detection | 4-layer stealth system (network, fingerprint, behavioral, session), adaptive calibration, detection signal monitoring, cohort-based device profiles |
| LLMs | Claude Sonnet 4.5 (code gen), Haiku 4.5 (DOM analysis), Opus 4.5 (complex reasoning) |
| Backend API | FastAPI (Python) |
| Frontend | React + TypeScript |
| Database | PostgreSQL (RDS), Redis (ElastiCache) |
| Object Storage | S3 (artifacts, raw data, audit logs) |
| Orchestration | MWAA Serverless (Free/Self-Service/Enterprise Base — YAML DAGs, EcsRunTaskOperator), MWAA Provisioned (Enterprise Dedicated — Python DAGs, PythonOperator, full Airflow UI) |
| Compute | ECS Fargate (agents + browsers) |
| IaC | Terraform or AWS CDK (TypeScript) |
| Auth | Amazon Cognito + custom RBAC |
| Proxy / Anti-Block | Bright Data or SmartProxy (residential + datacenter), geo-targeted per-pipeline, intra-tenant response caching (Redis + S3) |
| PII Detection | Microsoft Presidio or AWS Comprehend |
| Monitoring | CloudWatch, X-Ray, custom metrics |
| CI/CD | GitHub Actions → ECR → ECS |
| SDK Generation | OpenAPI spec → auto-generated clients |
| Secrets | AWS Secrets Manager (per-tenant namespaced) |
