"""Element fingerprinting for adaptive relocation (Tier 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


@dataclass
class ElementFingerprint:
    """Structural fingerprint of a DOM element for relocation."""

    identifier: str
    tag_name: str
    text_content: str
    attributes: dict[str, str] = field(default_factory=dict)
    sibling_tags: list[str] = field(default_factory=list)
    ancestor_path: list[str] = field(default_factory=list)
    parent_tag: str = ""
    parent_attributes: dict[str, str] = field(default_factory=dict)
    css_selector: str = ""
    xpath: str = ""


async def capture_fingerprint(page: Page, selector: str, identifier: str) -> ElementFingerprint:
    """Capture a fingerprint of the element matching the selector."""
    data = await page.evaluate(
        """(selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;

        const attrs = {};
        for (const attr of el.attributes) {
            attrs[attr.name] = attr.value;
        }

        const siblingTags = [];
        if (el.parentElement) {
            for (const child of el.parentElement.children) {
                siblingTags.push(child.tagName.toLowerCase());
            }
        }

        const ancestorPath = [];
        let current = el;
        while (current.parentElement) {
            ancestorPath.unshift(current.parentElement.tagName.toLowerCase());
            current = current.parentElement;
        }

        const parentAttrs = {};
        if (el.parentElement) {
            for (const attr of el.parentElement.attributes) {
                parentAttrs[attr.name] = attr.value;
            }
        }

        return {
            tagName: el.tagName.toLowerCase(),
            textContent: (el.textContent || '').trim().substring(0, 200),
            attributes: attrs,
            siblingTags: siblingTags,
            ancestorPath: ancestorPath,
            parentTag: el.parentElement ? el.parentElement.tagName.toLowerCase() : '',
            parentAttributes: parentAttrs,
        };
    }""",
        selector,
    )
    if data is None:
        msg = f"Element not found: {selector}"
        raise ValueError(msg)

    return ElementFingerprint(
        identifier=identifier,
        tag_name=data["tagName"],
        text_content=data["textContent"],
        attributes=data["attributes"],
        sibling_tags=data["siblingTags"],
        ancestor_path=data["ancestorPath"],
        parent_tag=data["parentTag"],
        parent_attributes=data["parentAttributes"],
        css_selector=selector,
    )


def score_similarity(fingerprint: ElementFingerprint, candidate: ElementFingerprint) -> float:
    """Score how similar two fingerprints are (0.0 to 1.0)."""
    score = 0.0

    # Tag name match: 0.15
    if fingerprint.tag_name == candidate.tag_name:
        score += 0.15

    # Text content similarity: 0.25
    score += 0.25 * _text_similarity(fingerprint.text_content, candidate.text_content)

    # Attribute overlap: 0.15
    score += 0.15 * _dict_similarity(fingerprint.attributes, candidate.attributes)

    # Sibling structure: 0.15
    score += 0.15 * _list_similarity(fingerprint.sibling_tags, candidate.sibling_tags)

    # Ancestor path: 0.20
    score += 0.20 * _list_similarity(fingerprint.ancestor_path, candidate.ancestor_path)

    # Parent match: 0.10
    parent_score = 0.0
    if fingerprint.parent_tag == candidate.parent_tag:
        parent_score = 0.5
        parent_score += 0.5 * _dict_similarity(fingerprint.parent_attributes, candidate.parent_attributes)
    score += 0.10 * parent_score

    return score


async def find_by_fingerprint(
    page: Page, fingerprint: ElementFingerprint, *, threshold: float = 0.6
) -> list[tuple[str, float]]:
    """Find elements on the page that match the fingerprint above threshold."""
    candidates_data = await page.evaluate(
        """() => {
        const elements = document.querySelectorAll('*');
        const results = [];
        for (const el of elements) {
            if (el.children.length > 10) continue;  // skip containers
            const attrs = {};
            for (const attr of el.attributes) {
                attrs[attr.name] = attr.value;
            }
            const siblingTags = [];
            if (el.parentElement) {
                for (const child of el.parentElement.children) {
                    siblingTags.push(child.tagName.toLowerCase());
                }
            }
            const ancestorPath = [];
            let current = el;
            while (current.parentElement) {
                ancestorPath.unshift(current.parentElement.tagName.toLowerCase());
                current = current.parentElement;
            }
            const parentAttrs = {};
            if (el.parentElement) {
                for (const attr of el.parentElement.attributes) {
                    parentAttrs[attr.name] = attr.value;
                }
            }

            // Generate a selector
            let selector = el.tagName.toLowerCase();
            if (el.id) selector = '#' + el.id;
            else if (el.className && typeof el.className === 'string') {
                const classes = el.className.trim().split(/\\s+/).filter(c => c);
                if (classes.length > 0) selector = el.tagName.toLowerCase() + '.' + classes.join('.');
            }

            results.push({
                selector: selector,
                tagName: el.tagName.toLowerCase(),
                textContent: (el.textContent || '').trim().substring(0, 200),
                attributes: attrs,
                siblingTags: siblingTags,
                ancestorPath: ancestorPath,
                parentTag: el.parentElement ? el.parentElement.tagName.toLowerCase() : '',
                parentAttributes: parentAttrs,
            });
        }
        return results;
    }"""
    )

    matches: list[tuple[str, float]] = []
    for data in candidates_data:
        candidate = ElementFingerprint(
            identifier="",
            tag_name=data["tagName"],
            text_content=data["textContent"],
            attributes=data["attributes"],
            sibling_tags=data["siblingTags"],
            ancestor_path=data["ancestorPath"],
            parent_tag=data["parentTag"],
            parent_attributes=data["parentAttributes"],
            css_selector=data["selector"],
        )
        sim = score_similarity(fingerprint, candidate)
        if sim >= threshold:
            matches.append((data["selector"], sim))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def _text_similarity(a: str, b: str) -> float:
    """Simple text similarity based on containment and length."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    a_lower, b_lower = a.lower(), b.lower()
    if a_lower == b_lower:
        return 1.0
    if a_lower in b_lower or b_lower in a_lower:
        return 0.7
    # Jaccard on words
    words_a = set(a_lower.split())
    words_b = set(b_lower.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _dict_similarity(a: dict[str, str], b: dict[str, str]) -> float:
    """Jaccard similarity on attribute name sets + value comparison."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    keys_a, keys_b = set(a.keys()), set(b.keys())
    shared = keys_a & keys_b
    union = keys_a | keys_b
    if not union:
        return 1.0
    name_sim = len(shared) / len(union)
    if not shared:
        return name_sim * 0.5
    value_matches = sum(1 for k in shared if a[k] == b[k])
    value_sim = value_matches / len(shared)
    return name_sim * 0.5 + value_sim * 0.5


def _list_similarity(a: list[str], b: list[str]) -> float:
    """Sequence similarity for ordered lists."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    max_len = max(len(a), len(b))
    matches = sum(1 for x, y in zip(a, b, strict=False) if x == y)
    return matches / max_len
