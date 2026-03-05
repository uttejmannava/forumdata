"""Forum Agent Orchestrator — LangGraph state machine for pipeline setup.

Usage:
    python -m forum_agents.orchestrator --url <url> --description <desc> [--output <dir>]
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from forum_browser.browser import BrowserConfig, ForumBrowser

from forum_schemas.models.pipeline import NavigationMode, StealthLevel

from forum_agents.agents.base import AgentContext
from forum_agents.agents.search import SearchResult, run_search
from forum_agents.llm_gateway import LlmGateway
from forum_agents.nav_modes.api_discovery import setup_api_discovery
from forum_agents.nav_modes.paginated import setup_paginated_list
from forum_agents.nav_modes.single_page import setup_single_page
from forum_agents.tools.compliance import check_source_blacklist
from forum_agents.tools.infra import save_code_artifact, save_config, save_metadata, save_schema


class PipelineSetupState(TypedDict):
    source_url: str
    user_description: str
    target_schema: dict[str, Any] | None
    search_result: dict[str, Any] | None
    compliance_result: dict[str, Any] | None
    navigation_result: dict[str, Any] | None
    extraction_result: dict[str, Any] | None
    navigation_mode: str
    stealth_level: str
    output_dir: str
    errors: Annotated[list[str], operator.add]
    status: str


async def analyze_source(state: PipelineSetupState) -> dict[str, Any]:
    """Run Search Agent to discover page type and data regions."""
    llm = LlmGateway(mock_responses=state.get("_mock_responses"))  # type: ignore[arg-type]
    ctx = AgentContext(
        source_url=state["source_url"],
        user_description=state["user_description"],
        llm=llm,
    )

    result = await run_search(ctx)

    if not result.success:
        return {
            "errors": result.errors,
            "status": "failed",
            "search_result": None,
        }

    return {
        "search_result": {
            "page_type": result.page_type,
            "api_candidates": result.api_candidates,
            "data_regions": result.data_regions,
            "pagination": result.pagination,
            "page_html": result.page_html,
            "has_llms_txt": result.has_llms_txt,
            "robots_allowed": result.robots_allowed,
        },
        "navigation_mode": result.recommended_nav_mode.value,
        "stealth_level": result.stealth_level.value,
        "status": "analyzed",
    }


async def check_compliance(state: PipelineSetupState) -> dict[str, Any]:
    """Run compliance checks."""
    if state["status"] == "failed":
        return {}

    search = state.get("search_result")
    if search and not search.get("robots_allowed", True):
        return {
            "compliance_result": {"allowed": False, "reason": "robots.txt disallowed"},
            "errors": ["COMPLIANCE_BLOCKED: robots.txt disallows access"],
            "status": "blocked",
        }

    # Check against empty blacklist for now (populated from DB in production)
    bl_result = await check_source_blacklist(state["source_url"], [])
    if not bl_result.allowed:
        return {
            "compliance_result": {"allowed": False, "reason": bl_result.reason},
            "errors": [f"COMPLIANCE_BLOCKED: {bl_result.reason}"],
            "status": "blocked",
        }

    return {
        "compliance_result": {"allowed": True, "reason": "All checks passed"},
        "status": "compliant",
    }


async def setup_extraction(state: PipelineSetupState) -> dict[str, Any]:
    """Dispatch to the appropriate navigation mode for extraction setup."""
    if state["status"] in ("failed", "blocked"):
        return {}

    llm = LlmGateway(mock_responses=state.get("_mock_responses"))  # type: ignore[arg-type]
    ctx = AgentContext(
        source_url=state["source_url"],
        user_description=state["user_description"],
        llm=llm,
        working_dir=state["output_dir"],
    )

    search_data = state.get("search_result") or {}
    search_result = SearchResult(
        success=True,
        page_type=search_data.get("page_type", "static_html"),
        api_candidates=search_data.get("api_candidates", []),
        data_regions=search_data.get("data_regions", []),
        pagination=search_data.get("pagination"),
        page_html=search_data.get("page_html", ""),
        has_llms_txt=search_data.get("has_llms_txt", False),
        robots_allowed=search_data.get("robots_allowed", True),
    )

    stealth = StealthLevel(state.get("stealth_level", "none"))
    browser_stealth = stealth if stealth != StealthLevel.NONE else StealthLevel.BASIC
    config = BrowserConfig(stealth_level=browser_stealth)

    try:
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto(state["source_url"], wait_until="networkidle", timeout=30000)

            nav_mode = state.get("navigation_mode", "SINGLE_PAGE")

            if nav_mode == NavigationMode.API_DISCOVERY:
                setup_result = await setup_api_discovery(ctx, search_result, page)
            elif nav_mode == NavigationMode.PAGINATED_LIST:
                setup_result = await setup_paginated_list(ctx, search_result, page)
            else:
                setup_result = await setup_single_page(ctx, search_result, page)

    except Exception as e:
        return {
            "errors": [f"EXTRACTION_FAILED: {e}"],
            "status": "failed",
        }

    if not setup_result.success:
        return {
            "errors": setup_result.errors,
            "status": "failed",
        }

    nav_data = None
    if setup_result.navigation:
        nav_data = {
            "navigation_code": setup_result.navigation.navigation_code,
            "pages_found": setup_result.navigation.pages_found,
        }

    ext_data = None
    if setup_result.extraction:
        ext_data = {
            "extraction_code": setup_result.extraction.extraction_code,
            "schema": setup_result.extraction.schema,
            "sample_data": setup_result.extraction.sample_data,
            "selectors": setup_result.extraction.selectors,
            "row_count": setup_result.extraction.row_count,
        }

    return {
        "navigation_result": nav_data,
        "extraction_result": ext_data,
        "status": "extracted",
    }


async def validate_output(state: PipelineSetupState) -> dict[str, Any]:
    """Validate that extraction produced usable results."""
    if state["status"] in ("failed", "blocked"):
        return {}

    ext = state.get("extraction_result")
    if not ext:
        return {"errors": ["EXTRACTION_FAILED: No extraction result"], "status": "failed"}

    code = ext.get("extraction_code", "")
    if not code:
        return {"errors": ["EXTRACTION_FAILED: Empty extraction code"], "status": "failed"}

    try:
        compile(code, "<validation>", "exec")
    except SyntaxError as e:
        return {"errors": [f"EXTRACTION_FAILED: Invalid Python: {e}"], "status": "failed"}

    return {"status": "validated"}


async def save_artifacts(state: PipelineSetupState) -> dict[str, Any]:
    """Write extraction code, schema, config to output directory."""
    if state["status"] in ("failed", "blocked"):
        return {}

    output = Path(state["output_dir"])
    ext = state.get("extraction_result") or {}
    nav = state.get("navigation_result") or {}

    # Save extraction code
    if ext.get("extraction_code"):
        save_code_artifact(ext["extraction_code"], output / "extract.py")

    # Save navigation code
    if nav.get("navigation_code"):
        save_code_artifact(nav["navigation_code"], output / "navigate.py")

    # Save schema
    if ext.get("schema"):
        save_schema(ext["schema"], output / "schema.json")

    # Save sample data
    if ext.get("sample_data"):
        (output / "sample_data.json").parent.mkdir(parents=True, exist_ok=True)
        (output / "sample_data.json").write_text(
            json.dumps(ext["sample_data"], indent=2, default=str), encoding="utf-8"
        )

    # Save config
    config_data = {
        "source_url": state["source_url"],
        "navigation_mode": state.get("navigation_mode", "SINGLE_PAGE"),
        "stealth_level": state.get("stealth_level", "none"),
    }
    save_config(config_data, output / "config.json")

    # Save metadata
    save_metadata(
        output / "metadata.json",
        navigation_mode=state.get("navigation_mode", "single_page"),
        stealth_level=state.get("stealth_level", "none"),
    )

    return {"status": "complete"}


def _should_continue(state: PipelineSetupState) -> str:
    """Route based on current status."""
    if state["status"] in ("failed", "blocked"):
        return END
    return "next"


def build_graph() -> StateGraph:  # type: ignore[type-arg]
    """Build the LangGraph state machine for pipeline setup."""
    graph = StateGraph(PipelineSetupState)

    graph.add_node("analyze_source", analyze_source)
    graph.add_node("check_compliance", check_compliance)
    graph.add_node("setup_extraction", setup_extraction)
    graph.add_node("validate_output", validate_output)
    graph.add_node("save_artifacts", save_artifacts)

    graph.add_edge(START, "analyze_source")
    graph.add_conditional_edges(
        "analyze_source",
        _should_continue,
        {"next": "check_compliance", END: END},
    )
    graph.add_conditional_edges(
        "check_compliance",
        _should_continue,
        {"next": "setup_extraction", END: END},
    )
    graph.add_conditional_edges(
        "setup_extraction",
        _should_continue,
        {"next": "validate_output", END: END},
    )
    graph.add_conditional_edges(
        "validate_output",
        _should_continue,
        {"next": "save_artifacts", END: END},
    )
    graph.add_edge("save_artifacts", END)

    return graph


async def run_setup(
    url: str,
    description: str,
    output_dir: str = "./output",
    schema_path: str | None = None,
) -> PipelineSetupState:
    """Run the full pipeline setup orchestration."""
    target_schema = None
    if schema_path:
        target_schema = json.loads(Path(schema_path).read_text())

    initial_state: PipelineSetupState = {
        "source_url": url,
        "user_description": description,
        "target_schema": target_schema,
        "search_result": None,
        "compliance_result": None,
        "navigation_result": None,
        "extraction_result": None,
        "navigation_mode": "",
        "stealth_level": "",
        "output_dir": output_dir,
        "errors": [],
        "status": "starting",
    }

    graph = build_graph()
    app = graph.compile()
    final_state = await app.ainvoke(initial_state)  # type: ignore[arg-type]
    return final_state  # type: ignore[return-value]
