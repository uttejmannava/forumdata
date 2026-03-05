"""Record browser interactions (requests, responses, DOM snapshots) for later replay."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import Page, Request, Response


@dataclass
class RecordedInteraction:
    """A single recorded request/response pair."""

    url: str
    method: str
    request_headers: dict[str, str] = field(default_factory=dict)
    response_status: int = 0
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body_b64: str = ""
    resource_type: str = ""
    timestamp_ms: float = 0.0


@dataclass
class RecordingSession:
    """A complete recorded browser session."""

    name: str
    target_url: str
    interactions: list[RecordedInteraction] = field(default_factory=list)
    dom_snapshots: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


class InteractionRecorder:
    """Records all browser network interactions for later replay."""

    def __init__(self, name: str) -> None:
        self._session = RecordingSession(name=name, target_url="")
        self._pending: dict[str, RecordedInteraction] = {}

    async def __aenter__(self) -> InteractionRecorder:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    def attach(self, page: Page) -> None:
        """Attach recording listeners to a page."""

        def on_request(request: Request) -> None:
            interaction = RecordedInteraction(
                url=request.url,
                method=request.method,
                request_headers=dict(request.headers),
                resource_type=request.resource_type,
            )
            self._pending[request.url] = interaction
            self._session.interactions.append(interaction)

        async def on_response(response: Response) -> None:
            url = response.request.url
            if url in self._pending:
                interaction = self._pending[url]
                interaction.response_status = response.status
                interaction.response_headers = dict(response.headers)
                try:
                    body = await response.body()
                    interaction.response_body_b64 = base64.b64encode(body).decode()
                except Exception:
                    pass

            if not self._session.target_url:
                self._session.target_url = url

        page.on("request", on_request)
        page.on("response", on_response)

    async def capture_dom_snapshot(self, page: Page, label: str | None = None) -> None:
        """Capture current page DOM for snapshot comparison."""
        content = await page.content()
        key = label or page.url
        self._session.dom_snapshots[key] = content

    def save(self, output_dir: Path) -> None:
        """Save recording to disk as JSON fixtures."""
        output_dir.mkdir(parents=True, exist_ok=True)

        interactions_data = []
        for i in self._session.interactions:
            interactions_data.append({
                "url": i.url,
                "method": i.method,
                "request_headers": i.request_headers,
                "response_status": i.response_status,
                "response_headers": i.response_headers,
                "response_body_b64": i.response_body_b64,
                "resource_type": i.resource_type,
                "timestamp_ms": i.timestamp_ms,
            })

        recording = {
            "name": self._session.name,
            "target_url": self._session.target_url,
            "interactions": interactions_data,
            "metadata": {k: v for k, v in self._session.metadata.items()},
        }
        (output_dir / "recording.json").write_text(json.dumps(recording, indent=2))

        for label, html in self._session.dom_snapshots.items():
            safe_name = label.replace("/", "_").replace(":", "_")[:100]
            (output_dir / f"dom_{safe_name}.html").write_text(html)

    @classmethod
    def load(cls, fixture_dir: Path) -> RecordingSession:
        """Load a previously saved recording."""
        recording_file = fixture_dir / "recording.json"
        data = json.loads(recording_file.read_text())

        interactions = []
        for i in data["interactions"]:
            interactions.append(RecordedInteraction(
                url=i["url"],
                method=i["method"],
                request_headers=i.get("request_headers", {}),
                response_status=i.get("response_status", 0),
                response_headers=i.get("response_headers", {}),
                response_body_b64=i.get("response_body_b64", ""),
                resource_type=i.get("resource_type", ""),
                timestamp_ms=i.get("timestamp_ms", 0.0),
            ))

        session = RecordingSession(
            name=data["name"],
            target_url=data["target_url"],
            interactions=interactions,
            metadata=data.get("metadata", {}),
        )

        # Load DOM snapshots
        for html_file in fixture_dir.glob("dom_*.html"):
            label = html_file.stem[4:]  # Strip "dom_" prefix
            session.dom_snapshots[label] = html_file.read_text()

        return session
