"""Detection signal monitoring — detect signs of bot detection before full blocking.

Maps to forum_schemas error taxonomy:
    DetectionSignal.CHALLENGE_PAGE → ErrorCode.DETECTION_BLOCKED
    DetectionSignal.RATE_LIMITED   → ErrorCode.RATE_LIMITED
    DetectionSignal.SOFT_BLOCK     → ErrorCode.ACCESS_BLOCKED
    DetectionSignal.THROTTLING     → WarningCode.DETECTION_SIGNAL
    DetectionSignal.COOKIE_CHALLENGE → WarningCode.DETECTION_SIGNAL
    DetectionSignal.FINGERPRINT_PROBE → WarningCode.DETECTION_SIGNAL
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from forum_schemas.models.errors import ErrorCode, WarningCode

if TYPE_CHECKING:
    from playwright.async_api import Page, Response


class DetectionSignal(enum.StrEnum):
    """Types of detection signals."""

    CHALLENGE_PAGE = "challenge_page"
    THROTTLING = "throttling"
    SOFT_BLOCK = "soft_block"
    COOKIE_CHALLENGE = "cookie_challenge"
    FINGERPRINT_PROBE = "fingerprint_probe"
    RATE_LIMITED = "rate_limited"


_SIGNAL_TO_ERROR: dict[DetectionSignal, ErrorCode | WarningCode] = {
    DetectionSignal.CHALLENGE_PAGE: ErrorCode.DETECTION_BLOCKED,
    DetectionSignal.RATE_LIMITED: ErrorCode.RATE_LIMITED,
    DetectionSignal.SOFT_BLOCK: ErrorCode.ACCESS_BLOCKED,
    DetectionSignal.THROTTLING: WarningCode.DETECTION_SIGNAL,
    DetectionSignal.COOKIE_CHALLENGE: WarningCode.DETECTION_SIGNAL,
    DetectionSignal.FINGERPRINT_PROBE: WarningCode.DETECTION_SIGNAL,
}


@dataclass
class DetectionEvent:
    """A recorded detection signal."""

    signal: DetectionSignal
    url: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, object] = field(default_factory=dict)
    response_status: int | None = None


_CHALLENGE_MARKERS = [
    "cf-browser-verification",
    "challenge-platform",
    "cf-challenge",
    "captcha",
    "recaptcha",
    "hcaptcha",
    "datadome",
    "just a moment",
    "checking your browser",
    "please verify you are a human",
]

_RATE_LIMIT_HEADERS = ["x-ratelimit-remaining", "retry-after", "x-rate-limit-remaining"]

_FINGERPRINT_PROBE_MARKERS = [
    "fingerprintjs",
    "fp2.min.js",
    "botd",
    "webgl-fingerprint",
    "canvas-fingerprint",
    "client-hints",
]

_COOKIE_CONSENT_CHALLENGE_INDICATORS = [
    "set-cookie",
]


class SignalMonitor:
    """Monitors for detection signals during browser sessions."""

    def __init__(self) -> None:
        self._events: list[DetectionEvent] = []
        self._response_times: list[float] = []

    async def check_response(self, response: Response) -> DetectionEvent | None:
        """Analyze an HTTP response for detection signals."""
        url = response.url
        status = response.status

        if status == 429:
            event = DetectionEvent(
                signal=DetectionSignal.RATE_LIMITED,
                url=url,
                response_status=status,
            )
            self._events.append(event)
            return event

        headers = response.headers
        for header in _RATE_LIMIT_HEADERS:
            val = headers.get(header)
            if val is not None and header == "x-ratelimit-remaining":
                try:
                    if int(val) <= 0:
                        event = DetectionEvent(
                            signal=DetectionSignal.RATE_LIMITED,
                            url=url,
                            response_status=status,
                            details={"header": header, "value": val},
                        )
                        self._events.append(event)
                        return event
                except ValueError:
                    pass

        if status == 403:
            event = DetectionEvent(
                signal=DetectionSignal.SOFT_BLOCK,
                url=url,
                response_status=status,
            )
            self._events.append(event)
            return event

        # Cookie challenge: Set-Cookie with redirect (3xx + cookie)
        if status is not None and 300 <= status < 400:
            set_cookie = headers.get("set-cookie")
            if set_cookie:
                event = DetectionEvent(
                    signal=DetectionSignal.COOKIE_CHALLENGE,
                    url=url,
                    response_status=status,
                    details={"set_cookie": set_cookie[:200]},
                )
                self._events.append(event)
                return event

        return None

    async def check_page_content(self, page: Page) -> DetectionEvent | None:
        """Analyze page content for challenge pages, CAPTCHAs, etc."""
        try:
            content = await page.content()
        except Exception:
            return None

        content_lower = content.lower()
        for marker in _CHALLENGE_MARKERS:
            if marker in content_lower:
                event = DetectionEvent(
                    signal=DetectionSignal.CHALLENGE_PAGE,
                    url=page.url,
                    details={"marker": marker},
                )
                self._events.append(event)
                return event

        # Fingerprint probe: unusual JS fingerprinting scripts loaded before content
        for marker in _FINGERPRINT_PROBE_MARKERS:
            if marker in content_lower:
                event = DetectionEvent(
                    signal=DetectionSignal.FINGERPRINT_PROBE,
                    url=page.url,
                    details={"marker": marker},
                )
                self._events.append(event)
                return event

        return None

    def record_response_time(self, elapsed_ms: float) -> bool:
        """Record response time, return True if throttling detected.

        Computes the rolling average of the last 10 samples *before* including
        the current sample, then flags if current > 3x that average.
        """
        if len(self._response_times) < 3:
            self._response_times.append(elapsed_ms)
            return False

        recent = self._response_times[-10:]
        avg = sum(recent) / len(recent)
        self._response_times.append(elapsed_ms)

        if elapsed_ms > avg * 3:
            event = DetectionEvent(
                signal=DetectionSignal.THROTTLING,
                url="",
                details={"elapsed_ms": elapsed_ms, "average_ms": avg},
            )
            self._events.append(event)
            return True
        return False

    @property
    def events(self) -> list[DetectionEvent]:
        """All recorded detection events."""
        return list(self._events)

    @property
    def is_detected(self) -> bool:
        """Whether any detection signals have been recorded."""
        return len(self._events) > 0

    def to_error_code(self, signal: DetectionSignal) -> ErrorCode | WarningCode:
        """Map a detection signal to the forum_schemas error taxonomy."""
        return _SIGNAL_TO_ERROR[signal]
