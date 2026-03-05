"""Tests for compliance check tools."""

from __future__ import annotations

import pytest

from forum_agents.tools.compliance import (
    _parse_robots_disallow,
    check_source_blacklist,
)


def test_parse_robots_disallow_match() -> None:
    robots = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /
"""
    rules = _parse_robots_disallow(robots, "/admin/settings")
    assert "/admin/" in rules


def test_parse_robots_disallow_no_match() -> None:
    robots = """
User-agent: *
Disallow: /admin/
"""
    rules = _parse_robots_disallow(robots, "/public/data")
    assert len(rules) == 0


def test_parse_robots_disallow_specific_agent() -> None:
    robots = """
User-agent: Googlebot
Disallow: /

User-agent: *
Disallow: /secret/
"""
    rules = _parse_robots_disallow(robots, "/public/data")
    assert len(rules) == 0


@pytest.mark.asyncio
async def test_check_source_blacklist_blocked() -> None:
    result = await check_source_blacklist(
        "https://blocked.example.com/data",
        ["example.com", "other.com"],
    )
    assert not result.allowed


@pytest.mark.asyncio
async def test_check_source_blacklist_allowed() -> None:
    result = await check_source_blacklist(
        "https://safe-site.com/data",
        ["example.com", "other.com"],
    )
    assert result.allowed


@pytest.mark.asyncio
async def test_check_source_blacklist_wildcard() -> None:
    result = await check_source_blacklist(
        "https://sub.blocked.com/data",
        ["*.blocked.com"],
    )
    assert not result.allowed


@pytest.mark.asyncio
async def test_check_source_blacklist_wildcard_no_match() -> None:
    result = await check_source_blacklist(
        "https://notblocked.com/data",
        ["*.blocked.com"],
    )
    assert result.allowed
