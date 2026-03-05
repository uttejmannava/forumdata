"""Network interception for API discovery mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page, Request, Response


_API_PATTERNS = ["/api/", "/v1/", "/v2/", "/v3/", "/graphql", "/rest/", "/_api/"]


@dataclass
class CapturedRequest:
    """A captured XHR/fetch request."""

    url: str
    method: str
    headers: dict[str, str] = field(default_factory=dict)
    post_data: str | None = None
    resource_type: str = ""
    response_status: int | None = None
    response_content_type: str | None = None
    response_body: str | None = None


class NetworkInterceptor:
    """Captures XHR/fetch requests for API discovery."""

    def __init__(self, *, max_body_size: int = 1024 * 1024) -> None:
        self._captured: list[CapturedRequest] = []
        self._max_body_size = max_body_size
        self._request_handler: object | None = None
        self._response_handler: object | None = None

    async def install(self, page: Page) -> None:
        """Install network listeners on the page."""
        pending: dict[str, CapturedRequest] = {}

        def on_request(request: Request) -> None:
            if request.resource_type in ("xhr", "fetch"):
                captured = CapturedRequest(
                    url=request.url,
                    method=request.method,
                    headers=dict(request.headers),
                    post_data=request.post_data,
                    resource_type=request.resource_type,
                )
                pending[request.url] = captured
                self._captured.append(captured)

        async def on_response(response: Response) -> None:
            request = response.request
            if request.url in pending:
                captured = pending[request.url]
                captured.response_status = response.status
                captured.response_content_type = response.headers.get("content-type")
                if captured.response_content_type and "json" in captured.response_content_type:
                    try:
                        body = await response.text()
                        if len(body) <= self._max_body_size:
                            captured.response_body = body
                    except Exception:
                        pass

        self._request_handler = on_request
        self._response_handler = on_response
        page.on("request", on_request)
        page.on("response", on_response)

    async def uninstall(self, page: Page) -> None:
        """Remove network listeners."""
        if self._request_handler:
            page.remove_listener("request", self._request_handler)
        if self._response_handler:
            page.remove_listener("response", self._response_handler)

    @property
    def captured_requests(self) -> list[CapturedRequest]:
        """All captured XHR/fetch requests."""
        return list(self._captured)

    def get_api_candidates(self) -> list[CapturedRequest]:
        """Filter captured requests to likely API endpoints."""
        candidates: list[CapturedRequest] = []
        for req in self._captured:
            if req.response_content_type and "json" in req.response_content_type:
                candidates.append(req)
                continue
            url_lower = req.url.lower()
            if any(pattern in url_lower for pattern in _API_PATTERNS):
                candidates.append(req)
        return candidates
