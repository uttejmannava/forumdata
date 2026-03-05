"""Replay recorded interactions by serving them via Playwright route handlers."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page, Route

    from forum_browser.testing.recorder import RecordingSession


class InteractionReplayer:
    """Replays recorded interactions as a mock server via Playwright route handlers."""

    def __init__(self, session: RecordingSession) -> None:
        self._session = session
        self._url_map: dict[str, int] = {}
        self._unmatched: list[str] = []
        self._matched_urls: set[str] = set()

        for idx, interaction in enumerate(session.interactions):
            if interaction.url not in self._url_map:
                self._url_map[interaction.url] = idx

    async def install(self, page: Page) -> None:
        """Install route handlers that serve recorded responses."""

        async def _handle(route: Route) -> None:
            url = route.request.url
            if url in self._url_map:
                idx = self._url_map[url]
                interaction = self._session.interactions[idx]
                self._matched_urls.add(url)
                body = base64.b64decode(interaction.response_body_b64) if interaction.response_body_b64 else b""
                await route.fulfill(
                    status=interaction.response_status,
                    headers=interaction.response_headers,
                    body=body,
                )
            else:
                self._unmatched.append(url)
                await route.abort()

        await page.route("**/*", _handle)

    async def uninstall(self, page: Page) -> None:
        """Remove replay route handlers."""
        await page.unroute("**/*")

    @property
    def unmatched_requests(self) -> list[str]:
        """URLs that were requested but had no matching recording."""
        return list(self._unmatched)

    @property
    def unused_recordings(self) -> list[str]:
        """URLs that were recorded but never requested during replay."""
        all_urls = {i.url for i in self._session.interactions}
        return sorted(all_urls - self._matched_urls)
