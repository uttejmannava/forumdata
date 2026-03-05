"""Content-based and structural similarity search (Tier 3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from playwright.async_api import Page


async def find_by_text(
    page: Page, text: str, *, exact: bool = False, case_sensitive: bool = False
) -> list[str]:
    """Locate elements by visible text content. Returns CSS selectors."""
    result = await page.evaluate(
        """({text, exact, caseSensitive}) => {
        const results = [];
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_ELEMENT
        );
        const searchText = caseSensitive ? text : text.toLowerCase();

        while (walker.nextNode()) {
            const el = walker.currentNode;
            const content = (el.textContent || '').trim();
            const compare = caseSensitive ? content : content.toLowerCase();

            let match = false;
            if (exact) {
                match = compare === searchText;
            } else {
                match = compare.includes(searchText);
            }

            if (match && el.children.length === 0) {
                let selector = el.tagName.toLowerCase();
                if (el.id) selector = '#' + el.id;
                else if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\\s+/).filter(c => c);
                    if (classes.length > 0) selector = el.tagName.toLowerCase() + '.' + classes.join('.');
                }
                results.push(selector);
            }
        }
        return results;
    }""",
        {"text": text, "exact": exact, "caseSensitive": case_sensitive},
    )
    return cast("list[str]", result)


async def find_by_regex(page: Page, pattern: str) -> list[str]:
    """Locate elements whose text content matches a regex pattern."""
    result = await page.evaluate(
        """(pattern) => {
        const regex = new RegExp(pattern);
        const results = [];
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_ELEMENT
        );

        while (walker.nextNode()) {
            const el = walker.currentNode;
            const content = (el.textContent || '').trim();
            if (regex.test(content) && el.children.length === 0) {
                let selector = el.tagName.toLowerCase();
                if (el.id) selector = '#' + el.id;
                else if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\\s+/).filter(c => c);
                    if (classes.length > 0) selector = el.tagName.toLowerCase() + '.' + classes.join('.');
                }
                results.push(selector);
            }
        }
        return results;
    }""",
        pattern,
    )
    return cast("list[str]", result)


async def find_similar(page: Page, reference_selector: str, *, threshold: float = 0.7) -> list[str]:
    """Find all elements structurally similar to the reference element."""
    result = await page.evaluate(
        """({selector, threshold}) => {
        const ref = document.querySelector(selector);
        if (!ref) return [];

        const refTag = ref.tagName;
        const refClasses = [...ref.classList];
        const refAttrNames = [...ref.attributes].map(a => a.name);
        const refParent = ref.parentElement;
        const refParentTag = refParent ? refParent.tagName : '';

        const results = [];
        const candidates = document.querySelectorAll(refTag);

        for (const el of candidates) {
            if (el === ref) continue;

            let score = 0;
            let maxScore = 4;

            // Same tag (always true since we queried by tag)
            score += 1;

            // Class overlap
            const elClasses = [...el.classList];
            if (refClasses.length > 0 && elClasses.length > 0) {
                const shared = refClasses.filter(c => elClasses.includes(c));
                score += shared.length / Math.max(refClasses.length, elClasses.length);
            } else if (refClasses.length === 0 && elClasses.length === 0) {
                score += 1;
            }

            // Parent tag match
            if (el.parentElement && el.parentElement.tagName === refParentTag) {
                score += 1;
            }

            // Attribute names overlap
            const elAttrNames = [...el.attributes].map(a => a.name);
            if (refAttrNames.length > 0) {
                const shared = refAttrNames.filter(a => elAttrNames.includes(a));
                score += shared.length / Math.max(refAttrNames.length, elAttrNames.length);
            } else if (elAttrNames.length === 0) {
                score += 1;
            }

            const similarity = score / maxScore;
            if (similarity >= threshold) {
                let sel = el.tagName.toLowerCase();
                if (el.id) sel = '#' + el.id;
                else if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\\s+/).filter(c => c);
                    if (classes.length > 0) sel = el.tagName.toLowerCase() + '.' + classes.join('.');
                }
                results.push(sel);
            }
        }
        return results;
    }""",
        {"selector": reference_selector, "threshold": threshold},
    )
    return cast("list[str]", result)


async def generate_selector(page: Page, element_description: str) -> str | None:
    """Auto-generate a CSS selector for an element identified by description."""
    result = await page.evaluate(
        """(description) => {
        const descLower = description.toLowerCase();
        const all = document.querySelectorAll('*');

        for (const el of all) {
            // Check id
            if (el.id && descLower.includes(el.id.toLowerCase())) {
                return '#' + el.id;
            }
            // Check data-testid
            const testid = el.getAttribute('data-testid');
            if (testid && descLower.includes(testid.toLowerCase())) {
                return '[data-testid="' + testid + '"]';
            }
        }

        // Try text content matching
        for (const el of all) {
            const text = (el.textContent || '').trim();
            if (text && descLower.includes(text.toLowerCase()) && el.children.length === 0) {
                if (el.id) return '#' + el.id;
                if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\\s+/).filter(c => c);
                    if (classes.length > 0) return el.tagName.toLowerCase() + '.' + classes.join('.');
                }
                return el.tagName.toLowerCase();
            }
        }

        return null;
    }""",
        element_description,
    )
    return cast("str | None", result)
