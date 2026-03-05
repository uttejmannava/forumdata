"""DOM analysis tools for page structure inspection."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Page

from forum_agents.tools.browser import ToolResult


async def get_accessibility_tree(page: Page, *, max_depth: int = 5) -> ToolResult:
    """Get a simplified accessibility tree as compact text for LLM analysis.

    Uses JavaScript to walk the DOM's computed accessibility roles and names,
    producing a compact text representation that fits in an LLM context window.
    """
    try:
        snapshot: dict[str, Any] | None = await page.evaluate(
            """(maxDepth) => {
            function walk(el, depth) {
                if (depth > maxDepth) return null;
                const role = el.getAttribute('role')
                    || {'A': 'link', 'BUTTON': 'button', 'INPUT': 'textbox',
                        'SELECT': 'combobox', 'TEXTAREA': 'textbox', 'IMG': 'img',
                        'H1': 'heading', 'H2': 'heading', 'H3': 'heading',
                        'H4': 'heading', 'H5': 'heading', 'H6': 'heading',
                        'TABLE': 'table', 'TR': 'row', 'TD': 'cell', 'TH': 'columnheader',
                        'NAV': 'navigation', 'MAIN': 'main', 'FORM': 'form',
                        'UL': 'list', 'OL': 'list', 'LI': 'listitem',
                       }[el.tagName] || '';
                const name = (el.getAttribute('aria-label')
                    || el.getAttribute('alt')
                    || el.getAttribute('title')
                    || (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                        ? el.textContent.trim().slice(0, 80) : ''));
                const children = Array.from(el.children)
                    .map(c => walk(c, depth + 1))
                    .filter(Boolean);
                if (!role && !name && children.length === 0) return null;
                return {role, name, children};
            }
            return walk(document.body, 0);
        }""",
            max_depth,
        )
        if snapshot is None:
            return ToolResult(success=True, data={"tree": "(empty page)", "node_count": 0})

        lines: list[str] = []
        _walk_a11y(snapshot, lines, depth=0, max_depth=max_depth)
        tree_text = "\n".join(lines)
        return ToolResult(success=True, data={"tree": tree_text, "node_count": len(lines)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


def _walk_a11y(node: dict[str, Any], lines: list[str], depth: int, max_depth: int) -> None:
    """Recursively walk accessibility tree, building compact text representation."""
    if depth > max_depth:
        return

    role = node.get("role", "")
    name = node.get("name", "")

    # Skip generic nodes with no useful info
    if not role and not name:
        for child in node.get("children", []):
            _walk_a11y(child, lines, depth, max_depth)
        return

    indent = "  " * depth
    parts = [f"{indent}[{role}]"] if role else [f"{indent}[-]"]
    if name:
        parts.append(f'"{name[:80]}"')
    lines.append(" ".join(parts))

    for child in node.get("children", []):
        _walk_a11y(child, lines, depth + 1, max_depth)


async def extract_text(page: Page, selector: str) -> ToolResult:
    """Extract visible text content from an element."""
    try:
        text = await page.text_content(selector, timeout=5000)
        return ToolResult(success=True, data={"text": text or "", "selector": selector})
    except Exception as e:
        return ToolResult(success=False, data={"selector": selector}, error=str(e))


async def find_elements(page: Page, selector: str) -> ToolResult:
    """Count and describe elements matching a selector."""
    try:
        elements = await page.query_selector_all(selector)
        descriptions: list[dict[str, Any]] = []
        for i, el in enumerate(elements[:20]):  # Cap at 20 to avoid huge outputs
            tag = await el.evaluate("e => e.tagName.toLowerCase()")
            text = (await el.text_content() or "")[:100]
            attrs = await el.evaluate(
                "e => Object.fromEntries(Array.from(e.attributes).map(a => [a.name, a.value]))"
            )
            descriptions.append({"index": i, "tag": tag, "text": text, "attributes": attrs})

        return ToolResult(
            success=True,
            data={"count": len(elements), "elements": descriptions, "selector": selector},
        )
    except Exception as e:
        return ToolResult(success=False, data={"selector": selector}, error=str(e))


async def get_page_structure(page: Page) -> ToolResult:
    """Get a condensed HTML skeleton (tags + classes + IDs, no text content)."""
    try:
        skeleton = await page.evaluate("""() => {
            function walk(el, depth) {
                if (depth > 6) return '';
                const tag = el.tagName.toLowerCase();
                const id = el.id ? '#' + el.id : '';
                const cls = el.className && typeof el.className === 'string'
                    ? '.' + el.className.trim().split(/\\s+/).join('.')
                    : '';
                const indent = '  '.repeat(depth);
                let result = indent + '<' + tag + id + cls + '>\\n';
                for (const child of el.children) {
                    result += walk(child, depth + 1);
                }
                return result;
            }
            return walk(document.body, 0);
        }""")
        return ToolResult(success=True, data={"skeleton": skeleton, "length": len(skeleton)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def get_tables(page: Page) -> ToolResult:
    """Extract all <table> elements as structured data."""
    try:
        tables_data: list[dict[str, Any]] = await page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            return Array.from(tables).map((table, idx) => {
                const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th'))
                    .map(th => th.textContent.trim());
                const rows = Array.from(table.querySelectorAll('tbody tr, tr'))
                    .slice(headers.length > 0 ? 0 : 1)
                    .map(tr => Array.from(tr.querySelectorAll('td'))
                        .map(td => td.textContent.trim()));
                return {
                    index: idx,
                    headers: headers,
                    row_count: rows.length,
                    sample_rows: rows.slice(0, 5),
                    id: table.id || null,
                    classes: table.className || null
                };
            });
        }""")
        return ToolResult(
            success=True,
            data={"tables": tables_data, "count": len(tables_data)},
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))
