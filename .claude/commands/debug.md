---
description: Debug issues by investigating API logs, pipeline runs, agent setup, and git history
---

# Debug

You are tasked with helping debug issues in the Forum platform. This command allows you to investigate problems across the API, pipeline stages, agent setup, and browser automation without editing files.

## Initial Response

When invoked WITH context (a file path or description):
```
I'll help debug issues with [context]. Let me understand the current state.

What specific problem are you encountering?
- What were you trying to test/implement?
- What went wrong?
- Any error messages?

I'll investigate logs, code, and git state to help figure out what's happening.
```

When invoked WITHOUT parameters:
```
I'll help debug your current issue.

Please describe what's going wrong:
- Which component is affected? (API, pipeline, agents, dashboard)
- What specific problem occurred?
- When did it last work?

I can investigate logs, code state, and recent changes to help identify the issue.
```

## Forum Components

| Component | Directory | Technology | Local Command |
|-----------|-----------|------------|---------------|
| API | `apps/api/` | FastAPI, SQLAlchemy, Alembic | `cd apps/api && FORUM_ENV=local uvicorn src.main:app --reload` |
| Dashboard | `apps/web/` | React, TypeScript, Vite | `cd apps/web && npm run dev` |
| Pipeline Runner | `packages/pipeline/` | Python, Playwright | `cd packages/pipeline && FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=extract python -m pipeline.runner` |
| Agent Orchestrator | `packages/agents/` | LangGraph, Playwright | `cd packages/agents && FORUM_ENV=local python -m agents.orchestrator --url "URL" --description "DESC"` |
| Browser Automation | `packages/browser/` | Playwright, anti-detection | Used by agents and pipeline |
| Schemas | `packages/schemas/` | Pydantic models | Shared types for all Python packages |
| SDKs | `packages/sdk-python/`, `packages/sdk-typescript/` | httpx, fetch | Auto-generated from OpenAPI |

**Local infrastructure**: `cd internal/debug && docker-compose up -d` (Postgres, Redis, LocalStack)

**When `FORUM_ENV=local`**: S3 → local filesystem, Secrets Manager → .env file, RDS → local Postgres

## Process Steps

### Step 1: Understand the Problem

After the user describes the issue:

1. **Read any provided context** (plan, file paths, error output):
   - Understand what they're implementing/testing
   - Note which component is affected
   - Identify expected vs actual behavior

2. **Quick state check**:
   - Current git branch and recent commits
   - Any uncommitted changes
   - When the issue started occurring

### Step 2: Investigate by Component

Spawn parallel Task agents for efficient investigation based on the affected component:

```
Task 1 - API Issues (if API-related):
1. Check recent changes to apps/api/
2. Look for error patterns in route handlers
3. Verify database migrations: check apps/api/alembic/
4. Run API tests: cd apps/api && pytest
5. Check middleware, auth, and error handling
Return: Key errors and relevant file:line references
```

```
Task 2 - Pipeline Stage Issues (if pipeline-related):
1. Identify which stage failed (Extract/Cleanse/Transform/Validate/Load/Notify)
2. Check stage-specific code in packages/pipeline/
3. Check error taxonomy in packages/schemas/src/models/errors.py
4. Try reproducing locally:
   FORUM_ENV=local TENANT_ID=X PIPELINE_ID=Y STAGE=extract python -m pipeline.runner
5. Run pipeline tests: cd packages/pipeline && pytest
Return: Stage failure details and relevant code references
```

```
Task 3 - Agent Setup Issues (if agent-related):
1. Review agent orchestrator code in packages/agents/
2. Check LLM gateway connectivity and configuration
3. Look at generated Playwright scripts
4. Check tool registry and sub-agent definitions
5. Run agent tests: cd packages/agents && pytest
Return: Agent configuration and error details
```

```
Task 4 - Extraction Code Issues (site changed / DOM broken):
1. Check code artifacts: tenants/{tenant_id}/pipelines/{pipeline_id}/code/v{n}/
2. Look for DOM selector changes
3. Check stealth level configuration (None/Basic/Standard/Aggressive)
4. Review anti-detection settings in packages/browser/
Return: DOM/selector analysis and stealth configuration
```

```
Task 5 - Git and File State:
1. git status and current branch
2. git log --oneline -10 for recent commits
3. git diff for uncommitted changes
4. Verify expected files exist
Return: Git state and any file issues
```

### Step 3: Present Findings

Based on the investigation, present a focused debug report:

```markdown
## Debug Report

### What's Wrong
[Clear statement of the issue based on evidence]

### Evidence Found

**From Code Analysis** (`[component directory]`):
- [Error/pattern found with file:line reference]
- [Configuration issue or missing dependency]

**From Tests**:
- [Test results and failures]
- [Missing test coverage]

**From Git/Files**:
- [Recent changes that might be related]
- [File state issues]

### Root Cause
[Most likely explanation based on evidence]

### Next Steps

1. **Try This First**:
   [Specific action or command]

2. **If That Doesn't Work**:
   - Check error taxonomy: packages/schemas/src/models/errors.py
   - Run all tests: turbo run test
   - Check infrastructure: cd internal/debug && docker-compose ps

### Can't Access?
Some issues might be outside my reach:
- Browser console errors (F12 in browser)
- AWS service issues (check CloudWatch)
- Network/proxy issues during extraction

Would you like me to investigate something specific further?
```

## Important Notes

- **Focus on the specific component** - Don't investigate everything, narrow down first
- **Always require problem description** - Can't debug without knowing what's wrong
- **Read files completely** - No limit/offset when reading context
- **Use the error taxonomy** - Check `packages/schemas/src/models/errors.py` for known error types
- **Guide back to user** - Some issues (browser console, AWS, live infrastructure) are outside reach
- **No file editing** - Pure investigation only

## Quick Reference

**Run Tests**:
```bash
turbo run test          # All packages
cd apps/api && pytest   # API only
cd packages/pipeline && pytest  # Pipeline only
cd packages/agents && pytest    # Agents only
cd apps/web && npm test         # Frontend only
```

**Local Pipeline Stage**:
```bash
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=extract python -m pipeline.runner
FORUM_ENV=local TENANT_ID=acme PIPELINE_ID=pip_cme STAGE=all python -m pipeline.runner
```

**Internal CLI** (if available):
```bash
forum-internal pipeline runs --tenant X --pipeline Y --last 10
forum-internal pipeline logs --tenant X --run run_abc
forum-internal trace view --run run_abc
forum-internal replay --run run_abc
forum-internal code pull --tenant X --pipeline Y
```

**Error Taxonomy**: `packages/schemas/src/models/errors.py`
- SOURCE_UNAVAILABLE, ACCESS_BLOCKED, SCHEMA_MISMATCH, etc.

**Code Artifacts**: `tenants/{tenant_id}/pipelines/{pipeline_id}/code/v{n}/`

**Git State**:
```bash
git status
git log --oneline -10
git diff
```
