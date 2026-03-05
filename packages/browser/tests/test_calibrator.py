"""Tests for stealth calibrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.http import HttpResponse
from forum_browser.stealth.calibrator import CalibrationProbe, StealthCalibrator


class TestCalibrationProbe:
    def test_successful_probe(self) -> None:
        probe = CalibrationProbe(
            level=StealthLevel.NONE,
            success=True,
            status_code=200,
            content_hash="abc123",
        )
        assert probe.success
        assert probe.detection_signals == []

    def test_failed_probe(self) -> None:
        probe = CalibrationProbe(
            level=StealthLevel.BASIC,
            success=False,
            detection_signals=["challenge_page"],
        )
        assert not probe.success

    def test_probe_with_response_time(self) -> None:
        probe = CalibrationProbe(
            level=StealthLevel.NONE,
            success=True,
            response_time_ms=150.5,
        )
        assert probe.response_time_ms == 150.5


class TestStealthCalibrator:
    async def test_calibrate_recommends_none_for_simple_page(self) -> None:
        """Calibrating against a simple data page should recommend NONE."""
        mock_response = HttpResponse(
            status_code=200,
            headers={"content-type": "text/html"},
            text="<html><body><h1>Herman Melville - Moby Dick</h1></body></html>",
            url="https://example.com/html",
            elapsed_ms=100.0,
        )

        calibrator = StealthCalibrator()
        with patch.object(calibrator, "_probe_with_http") as mock_probe:
            mock_probe.return_value = CalibrationProbe(
                level=StealthLevel.NONE,
                success=True,
                status_code=200,
                content_hash="abc123",
            )
            result = await calibrator.calibrate("https://example.com/html")
            assert result.recommended_level == StealthLevel.NONE
            assert StealthLevel.NONE in result.levels_tested
            assert result.results["none"].success is True

    async def test_calibrate_stops_at_first_success(self) -> None:
        """Calibrator should stop at the first level that succeeds."""
        calibrator = StealthCalibrator()
        with patch.object(calibrator, "_probe_with_http") as mock_probe:
            mock_probe.return_value = CalibrationProbe(
                level=StealthLevel.NONE,
                success=True,
                status_code=200,
            )
            result = await calibrator.calibrate("https://example.com/html", max_level=StealthLevel.BASIC)
            assert result.recommended_level == StealthLevel.NONE
            assert len(result.levels_tested) == 1

    async def test_calibrate_escalates_on_failure(self) -> None:
        """When NONE fails, calibrator should escalate to BASIC."""
        calibrator = StealthCalibrator()
        with (
            patch.object(calibrator, "_probe_with_http") as mock_http,
            patch.object(calibrator, "_probe_with_browser") as mock_browser,
        ):
            mock_http.return_value = CalibrationProbe(
                level=StealthLevel.NONE,
                success=False,
                detection_signals=["challenge_page"],
            )
            mock_browser.return_value = CalibrationProbe(
                level=StealthLevel.BASIC,
                success=True,
                status_code=200,
            )
            result = await calibrator.calibrate("https://protected.example.com", max_level=StealthLevel.STANDARD)
            assert result.recommended_level == StealthLevel.BASIC
            assert len(result.levels_tested) == 2
            assert StealthLevel.NONE in result.levels_tested
            assert StealthLevel.BASIC in result.levels_tested

    async def test_calibrate_returns_aggressive_when_all_fail(self) -> None:
        """When all levels fail, returns AGGRESSIVE as the default."""
        calibrator = StealthCalibrator()
        with (
            patch.object(calibrator, "_probe_with_http") as mock_http,
            patch.object(calibrator, "_probe_with_browser") as mock_browser,
        ):
            mock_http.return_value = CalibrationProbe(level=StealthLevel.NONE, success=False)
            mock_browser.return_value = CalibrationProbe(level=StealthLevel.BASIC, success=False)
            result = await calibrator.calibrate("https://fortress.example.com", max_level=StealthLevel.BASIC)
            assert result.recommended_level == StealthLevel.AGGRESSIVE
            assert len(result.levels_tested) == 2

    async def test_is_success(self) -> None:
        calibrator = StealthCalibrator()
        assert calibrator._is_success(CalibrationProbe(level=StealthLevel.NONE, success=True))
        assert not calibrator._is_success(CalibrationProbe(level=StealthLevel.NONE, success=False))

    async def test_calibration_order(self) -> None:
        """Levels should be tested in order: None -> Basic -> Standard -> Aggressive."""
        tested_levels: list[StealthLevel] = []
        calibrator = StealthCalibrator()

        async def track_http(url: str) -> CalibrationProbe:
            tested_levels.append(StealthLevel.NONE)
            return CalibrationProbe(level=StealthLevel.NONE, success=False)

        async def track_browser(url: str, level: StealthLevel) -> CalibrationProbe:
            tested_levels.append(level)
            return CalibrationProbe(level=level, success=False)

        with (
            patch.object(calibrator, "_probe_with_http", side_effect=track_http),
            patch.object(calibrator, "_probe_with_browser", side_effect=track_browser),
        ):
            await calibrator.calibrate("https://example.com")
            assert tested_levels == [
                StealthLevel.NONE,
                StealthLevel.BASIC,
                StealthLevel.STANDARD,
                StealthLevel.AGGRESSIVE,
            ]
