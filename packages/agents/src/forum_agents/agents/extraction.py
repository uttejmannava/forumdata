"""Extraction Agent — selector generation and extraction code output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

from forum_browser.resolution.cascade import ResolutionResult
from forum_browser.resolution.fingerprints import ElementFingerprint, capture_fingerprint
from forum_browser.resolution.storage import FingerprintStorage

from forum_agents.agents.base import AgentContext, AgentResult
from forum_agents.agents.search import SearchResult
from forum_agents.llm_gateway import AgentRole
from forum_agents.prompts import extraction_codegen, schema_inference
from forum_agents.tools.dom import get_tables


@dataclass
class ExtractionResult(AgentResult):
    """Result from the Extraction Agent."""

    extraction_code: str = ""
    schema: dict[str, Any] = field(default_factory=dict)
    sample_data: list[dict[str, Any]] = field(default_factory=list)
    selectors: dict[str, str] = field(default_factory=dict)
    row_count: int = 0


async def run_extraction(
    ctx: AgentContext,
    search_result: SearchResult,
    page: Page,
    sample_html: str,
    *,
    target_schema: dict[str, Any] | None = None,
    storage: FingerprintStorage | None = None,
) -> ExtractionResult:
    """Generate extraction code from page analysis."""
    result = ExtractionResult(success=False)
    total_input = 0
    total_output = 0

    try:
        # 1. Detect tables in the page
        tables = await get_tables(page)
        tables_data = tables.data.get("tables", []) if tables.success else []

        # 2. Infer or validate schema
        schema_system = schema_inference.build_system_prompt()
        schema_user = schema_inference.build_user_message(
            user_description=ctx.user_description,
            sample_html=sample_html[:12000],
            tables_data=tables_data,
            existing_schema=target_schema,
        )

        schema_response = await ctx.llm.complete(
            AgentRole.SCHEMA_INFERENCE,
            schema_system,
            [{"role": "user", "content": schema_user}],
        )
        total_input += schema_response.input_tokens
        total_output += schema_response.output_tokens

        schema = _parse_json_response(schema_response.content)
        result.schema = schema

        # 3. Generate extraction code
        extract_system = extraction_codegen.build_system_prompt()
        extract_user = extraction_codegen.build_user_message(
            user_description=ctx.user_description,
            sample_html=sample_html[:12000],
            schema=schema,
            data_regions=search_result.data_regions if search_result.data_regions else None,
        )

        extract_response = await ctx.llm.complete(
            AgentRole.EXTRACTION_CODEGEN,
            extract_system,
            [{"role": "user", "content": extract_user}],
        )
        total_input += extract_response.input_tokens
        total_output += extract_response.output_tokens

        code = _clean_code(extract_response.content)

        # Validate syntax
        try:
            compile(code, "<extraction>", "exec")
        except SyntaxError as e:
            result.errors.append(f"EXTRACTION_FAILED: Generated code has syntax error: {e}")
            result.extraction_code = code
            result.llm_calls = 2
            result.total_tokens = total_input + total_output
            return result

        result.extraction_code = code

        # 4. Extract SELECTORS dict from generated code
        result.selectors = _extract_selectors(code)

        # 5. Execute extraction to get sample data
        sample_data = await _execute_extraction(page, code)
        result.sample_data = sample_data
        result.row_count = len(sample_data)

        # 6. Save fingerprints for self-healing
        if storage and result.selectors:
            for field_name, selector in result.selectors.items():
                try:
                    fp = await capture_fingerprint(page, selector, field_name)
                    await storage.save(ctx.tenant_id, ctx.pipeline_id, field_name, fp)
                except Exception:
                    pass  # Non-critical — fingerprint save failure doesn't block setup

        result.llm_calls = 2
        result.total_tokens = total_input + total_output
        result.success = True

    except Exception as e:
        result.errors.append(f"EXTRACTION_FAILED: {e}")
        result.llm_calls = 2
        result.total_tokens = total_input + total_output

    return result


async def llm_relocate(
    page: Page,
    fingerprint: ElementFingerprint,
    context: dict[str, Any],
) -> ResolutionResult | None:
    """Tier 4 — LLM semantic relocation.

    Invoked by ResolutionCascade when Tiers 1-3 fail.
    Requires an LlmGateway in the context dict.
    """
    from forum_agents.tools.dom import get_accessibility_tree, get_page_structure

    llm = context.get("llm")
    if llm is None:
        return None

    a11y = await get_accessibility_tree(page)
    structure = await get_page_structure(page)

    prompt = (
        f"An element has moved on the page. Help me find it.\n\n"
        f"Original selector: {fingerprint.css_selector}\n"
        f"Original tag: {fingerprint.tag_name}\n"
        f"Original text: {fingerprint.text_content[:200]}\n"
        f"Original ancestor path: {' > '.join(fingerprint.ancestor_path)}\n\n"
        f"Current page accessibility tree:\n{a11y.data.get('tree', '')[:4000]}\n\n"
        f"Current page structure:\n{structure.data.get('skeleton', '')[:2000]}\n\n"
        f"Respond with JSON: {{\"selector\": \"new_css_selector\", \"confidence\": 0.0-1.0}}"
    )

    try:
        response = await llm.complete(
            AgentRole.CHANGE_DETECTION,
            "You find relocated elements on changed web pages. Respond with JSON only.",
            [{"role": "user", "content": prompt}],
        )

        data = _parse_json_response(response.content)
        selector = data.get("selector")
        confidence = float(data.get("confidence", 0.0))

        if selector and confidence > 0.3:
            from forum_browser.resolution.cascade import ResolutionResult, ResolutionTier

            return ResolutionResult(
                selector=selector,
                tier=ResolutionTier.LLM_RELOCATION,
                confidence=confidence,
                element_count=1,
                metadata={"original_selector": fingerprint.css_selector},
            )
    except Exception:
        pass

    return None


def _parse_json_response(content: str) -> dict[str, Any]:
    """Parse LLM JSON response."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return {}


def _clean_code(content: str) -> str:
    """Strip markdown fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return text.strip()


def _extract_selectors(code: str) -> dict[str, str]:
    """Extract the SELECTORS dict from generated code."""
    namespace: dict[str, Any] = {}
    try:
        exec(code, namespace)  # noqa: S102
        selectors = namespace.get("SELECTORS", {})
        if isinstance(selectors, dict):
            return {str(k): str(v) for k, v in selectors.items()}
    except Exception:
        pass
    return {}


async def _execute_extraction(page: Page, code: str) -> list[dict[str, Any]]:
    """Execute generated extraction code and return sample data."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102

    extract_fn = namespace.get("extract")
    if extract_fn is None:
        return []

    try:
        data = await extract_fn(page)
        if isinstance(data, list):
            return [dict(row) for row in data[:100]]
    except Exception:
        pass

    return []
