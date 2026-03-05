"""Pre-extraction compliance check tools."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from forum_browser.http import StealthHttpClient

from forum_schemas.models.pipeline import StealthLevel


@dataclass
class ComplianceCheckResult:
    """Result from a compliance check."""

    allowed: bool
    reason: str
    recommended_stealth: StealthLevel | None = None
    details: dict[str, Any] = field(default_factory=dict)


async def check_robots_txt(url: str) -> ComplianceCheckResult:
    """Fetch and parse robots.txt, check if URL is allowed."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    path = parsed.path or "/"

    try:
        async with StealthHttpClient() as client:
            resp = await client.get(robots_url)

        if resp.status_code == 404:
            return ComplianceCheckResult(
                allowed=True,
                reason="No robots.txt found",
                details={"robots_url": robots_url, "status": 404},
            )

        if resp.status_code != 200:
            return ComplianceCheckResult(
                allowed=True,
                reason=f"robots.txt returned status {resp.status_code}",
                details={"robots_url": robots_url, "status": resp.status_code},
            )

        # Parse robots.txt for User-agent: * directives
        disallowed = _parse_robots_disallow(resp.text, path)
        if disallowed:
            return ComplianceCheckResult(
                allowed=False,
                reason=f"Path {path} is disallowed by robots.txt",
                recommended_stealth=StealthLevel.STANDARD,
                details={"robots_url": robots_url, "disallow_rules": disallowed},
            )

        return ComplianceCheckResult(
            allowed=True,
            reason="Path allowed by robots.txt",
            recommended_stealth=StealthLevel.NONE,
            details={"robots_url": robots_url},
        )
    except Exception as e:
        return ComplianceCheckResult(
            allowed=True,
            reason=f"Could not fetch robots.txt: {e}",
            details={"robots_url": robots_url, "error": str(e)},
        )


def _parse_robots_disallow(robots_text: str, path: str) -> list[str]:
    """Parse robots.txt and return matching Disallow rules for User-agent: *."""
    in_wildcard_section = False
    disallow_rules: list[str] = []

    for line in robots_text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue

        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            in_wildcard_section = agent == "*"
            continue

        if in_wildcard_section and line.lower().startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule and path.startswith(rule):
                disallow_rules.append(rule)

    return disallow_rules


async def check_llms_txt(url: str) -> ComplianceCheckResult:
    """Check for llms.txt and parse machine-access permissions."""
    parsed = urlparse(url)
    llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"

    try:
        async with StealthHttpClient() as client:
            resp = await client.get(llms_url)

        if resp.status_code == 404:
            return ComplianceCheckResult(
                allowed=True,
                reason="No llms.txt found",
                details={"llms_url": llms_url, "has_llms_txt": False},
            )

        if resp.status_code == 200:
            # llms.txt present — machine access explicitly defined
            endpoints = _parse_llms_txt(resp.text)
            return ComplianceCheckResult(
                allowed=True,
                reason="llms.txt found — machine access defined",
                recommended_stealth=StealthLevel.NONE,
                details={
                    "llms_url": llms_url,
                    "has_llms_txt": True,
                    "endpoints": endpoints,
                    "raw": resp.text[:2000],
                },
            )

        return ComplianceCheckResult(
            allowed=True,
            reason=f"llms.txt returned status {resp.status_code}",
            details={"llms_url": llms_url, "status": resp.status_code},
        )
    except Exception as e:
        return ComplianceCheckResult(
            allowed=True,
            reason=f"Could not fetch llms.txt: {e}",
            details={"llms_url": llms_url, "error": str(e)},
        )


def _parse_llms_txt(text: str) -> list[str]:
    """Extract endpoint URLs from llms.txt content."""
    urls: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
        # Also look for markdown-style links
        md_urls = re.findall(r"\((https?://[^\)]+)\)", line)
        urls.extend(md_urls)
    return urls


async def check_source_blacklist(url: str, blacklist: list[str]) -> ComplianceCheckResult:
    """Check URL against a domain/pattern blacklist."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for pattern in blacklist:
        pattern = pattern.lower().strip()
        if pattern.startswith("*."):
            # Wildcard subdomain match
            base = pattern[2:]
            if domain == base or domain.endswith("." + base):
                return ComplianceCheckResult(
                    allowed=False,
                    reason=f"Domain {domain} matches blacklist pattern {pattern}",
                    details={"domain": domain, "matched_pattern": pattern},
                )
        elif domain == pattern or domain.endswith("." + pattern):
            return ComplianceCheckResult(
                allowed=False,
                reason=f"Domain {domain} is blacklisted",
                details={"domain": domain, "matched_pattern": pattern},
            )

    return ComplianceCheckResult(
        allowed=True,
        reason="URL not on blacklist",
        details={"domain": domain, "blacklist_size": len(blacklist)},
    )
