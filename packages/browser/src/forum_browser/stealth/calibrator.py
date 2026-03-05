"""Adaptive stealth calibrator — auto-detect minimum required stealth level."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.http import HttpClientConfig, StealthHttpClient
from forum_browser.stealth.profiles import ProfileLibrary
from forum_browser.stealth.signals import SignalMonitor
from forum_schemas.models.pipeline import StealthLevel


@dataclass
class CalibrationProbe:
    """Result of probing a URL at a specific stealth level."""

    level: StealthLevel
    success: bool
    status_code: int | None = None
    detection_signals: list[str] = field(default_factory=list)
    response_time_ms: float | None = None
    content_hash: str | None = None


@dataclass
class CalibrationResult:
    """Result of stealth calibration for a target URL."""

    recommended_level: StealthLevel
    levels_tested: list[StealthLevel] = field(default_factory=list)
    results: dict[str, CalibrationProbe] = field(default_factory=dict)


_STEALTH_ORDER = [
    StealthLevel.NONE,
    StealthLevel.BASIC,
    StealthLevel.STANDARD,
    StealthLevel.AGGRESSIVE,
]


class StealthCalibrator:
    """Probes a target URL with increasing stealth levels to find the minimum required."""

    async def calibrate(
        self, url: str, *, max_level: StealthLevel = StealthLevel.AGGRESSIVE
    ) -> CalibrationResult:
        """Probe URL with increasing stealth levels."""
        result = CalibrationResult(recommended_level=StealthLevel.AGGRESSIVE)
        max_idx = _STEALTH_ORDER.index(max_level)

        for level in _STEALTH_ORDER[: max_idx + 1]:
            result.levels_tested.append(level)
            if level == StealthLevel.NONE:
                probe = await self._probe_with_http(url)
            else:
                probe = await self._probe_with_browser(url, level)
            result.results[level.value] = probe

            if self._is_success(probe):
                result.recommended_level = level
                break

        return result

    async def _probe_with_http(self, url: str) -> CalibrationProbe:
        """Probe using curl_cffi (stealth level None)."""
        try:
            config = HttpClientConfig()
            async with StealthHttpClient(config) as client:
                response = await client.get(url)
                content_hash = hashlib.md5(response.text.encode()).hexdigest()  # noqa: S324
                signals: list[str] = []

                content_lower = response.text.lower()
                challenge_markers = ["captcha", "challenge", "cf-browser-verification", "checking your browser"]
                for marker in challenge_markers:
                    if marker in content_lower:
                        signals.append(marker)

                return CalibrationProbe(
                    level=StealthLevel.NONE,
                    success=response.status_code == 200 and not signals,
                    status_code=response.status_code,
                    detection_signals=signals,
                    response_time_ms=response.elapsed_ms,
                    content_hash=content_hash,
                )
        except Exception as e:
            return CalibrationProbe(
                level=StealthLevel.NONE,
                success=False,
                detection_signals=[str(e)],
            )

    async def _probe_with_browser(self, url: str, level: StealthLevel) -> CalibrationProbe:
        """Probe using browser at specified stealth level.

        For Standard and Aggressive levels, a device profile is loaded from the
        profile library so that fingerprint injection and TLS browser args are
        actually applied — making the probe representative of real stealth behavior.
        """
        try:
            profile = None
            if level in (StealthLevel.STANDARD, StealthLevel.AGGRESSIVE):
                try:
                    library = ProfileLibrary()
                    profile = library.get_profile()
                except (ValueError, FileNotFoundError):
                    pass  # No profiles available — probe without one

            config = BrowserConfig(
                stealth_level=level,
                headless=True,
                resource_blocking_enabled=True,
                device_profile=profile,
            )
            async with ForumBrowser(config) as browser:
                page = await browser.new_page()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                status = response.status if response else None
                content = await page.content()
                content_hash = hashlib.md5(content.encode()).hexdigest()  # noqa: S324

                monitor = SignalMonitor()
                event = await monitor.check_page_content(page)
                signals = [event.signal.value] if event else []

                return CalibrationProbe(
                    level=level,
                    success=status == 200 and not signals,
                    status_code=status,
                    detection_signals=signals,
                    content_hash=content_hash,
                )
        except Exception as e:
            return CalibrationProbe(
                level=level,
                success=False,
                detection_signals=[str(e)],
            )

    def _is_success(self, probe: CalibrationProbe) -> bool:
        """Determine if a probe succeeded without detection."""
        return probe.success
