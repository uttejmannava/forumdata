"""Tests for device profile library."""

from __future__ import annotations

from pathlib import Path

import pytest

from forum_browser.stealth.profiles import DeviceProfile, OperatingSystem, ProfileLibrary


class TestProfileLibrary:
    def test_load_profiles(self) -> None:
        lib = ProfileLibrary()
        profiles = lib.list_profiles()
        assert len(profiles) == 20  # 5 per file * 4 files

    def test_filter_by_os(self) -> None:
        lib = ProfileLibrary()
        windows = lib.list_profiles(os=OperatingSystem.WINDOWS)
        assert len(windows) == 5
        macos = lib.list_profiles(os=OperatingSystem.MACOS)
        assert len(macos) == 10  # chrome + safari

    def test_get_profile_by_id(self) -> None:
        lib = ProfileLibrary()
        profile = lib.get_profile_by_id("win11_chrome_desktop_1")
        assert profile.os == OperatingSystem.WINDOWS
        assert profile.browser == "chrome"
        assert profile.viewport_width == 1920

    def test_get_profile_by_id_not_found(self) -> None:
        lib = ProfileLibrary()
        with pytest.raises(KeyError):
            lib.get_profile_by_id("nonexistent")

    def test_get_random_profile(self) -> None:
        lib = ProfileLibrary()
        profile = lib.get_profile(os=OperatingSystem.LINUX)
        assert profile.os == OperatingSystem.LINUX
        assert profile.browser == "firefox"

    def test_get_profile_filter_browser(self) -> None:
        lib = ProfileLibrary()
        profile = lib.get_profile(browser="safari")
        assert profile.browser == "safari"
        assert profile.os == OperatingSystem.MACOS

    def test_get_profile_no_match(self) -> None:
        lib = ProfileLibrary()
        with pytest.raises(ValueError, match="No profiles found"):
            lib.get_profile(browser="opera")

    def test_profile_consistency(self) -> None:
        """Verify profiles have internally consistent data."""
        lib = ProfileLibrary()
        for pid in lib.list_profiles():
            profile = lib.get_profile_by_id(pid)
            assert profile.viewport_width <= profile.screen_width
            assert profile.viewport_height <= profile.screen_height
            assert profile.hardware_concurrency > 0
            assert profile.device_memory > 0
            assert len(profile.user_agent) > 10
            assert len(profile.fonts) > 0

    def test_custom_profiles_dir(self, tmp_path: Path) -> None:
        lib = ProfileLibrary(profiles_dir=tmp_path)
        assert lib.list_profiles() == []
