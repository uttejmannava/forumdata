"""Cohort-based device profiles with internally consistent fingerprints."""

from __future__ import annotations

import enum
import json
import random
from dataclasses import dataclass, field
from pathlib import Path


class OperatingSystem(enum.StrEnum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


@dataclass(frozen=True)
class DeviceProfile:
    """Internally consistent device fingerprint."""

    profile_id: str
    os: OperatingSystem
    browser: str
    user_agent: str
    viewport_width: int
    viewport_height: int
    screen_width: int
    screen_height: int
    device_pixel_ratio: float
    platform: str
    hardware_concurrency: int
    device_memory: int
    timezone: str
    locale: str
    fonts: list[str] = field(default_factory=list)
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    canvas_noise_seed: int = 0


class ProfileLibrary:
    """Manages a library of real device profiles loaded from JSON files."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._profiles_dir = profiles_dir or Path(__file__).parent.parent.parent.parent / "profiles"
        self._profiles: dict[str, DeviceProfile] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._profiles_dir.exists():
            return
        for json_file in self._profiles_dir.glob("*.json"):
            with open(json_file) as f:
                entries = json.load(f)
            for entry in entries:
                profile = DeviceProfile(
                    profile_id=entry["profile_id"],
                    os=OperatingSystem(entry["os"]),
                    browser=entry["browser"],
                    user_agent=entry["user_agent"],
                    viewport_width=entry["viewport_width"],
                    viewport_height=entry["viewport_height"],
                    screen_width=entry["screen_width"],
                    screen_height=entry["screen_height"],
                    device_pixel_ratio=entry["device_pixel_ratio"],
                    platform=entry["platform"],
                    hardware_concurrency=entry["hardware_concurrency"],
                    device_memory=entry["device_memory"],
                    timezone=entry["timezone"],
                    locale=entry["locale"],
                    fonts=entry.get("fonts", []),
                    webgl_vendor=entry.get("webgl_vendor", ""),
                    webgl_renderer=entry.get("webgl_renderer", ""),
                    canvas_noise_seed=entry.get("canvas_noise_seed", 0),
                )
                self._profiles[profile.profile_id] = profile

    def get_profile(self, *, os: OperatingSystem | None = None, browser: str | None = None) -> DeviceProfile:
        """Get a random profile matching the criteria."""
        self._ensure_loaded()
        candidates = list(self._profiles.values())
        if os is not None:
            candidates = [p for p in candidates if p.os == os]
        if browser is not None:
            candidates = [p for p in candidates if p.browser == browser]
        if not candidates:
            msg = f"No profiles found matching os={os}, browser={browser}"
            raise ValueError(msg)
        return random.choice(candidates)

    def get_profile_by_id(self, profile_id: str) -> DeviceProfile:
        """Get a specific profile by ID."""
        self._ensure_loaded()
        if profile_id not in self._profiles:
            msg = f"Profile not found: {profile_id}"
            raise KeyError(msg)
        return self._profiles[profile_id]

    def list_profiles(self, *, os: OperatingSystem | None = None) -> list[str]:
        """List available profile IDs."""
        self._ensure_loaded()
        if os is not None:
            return [pid for pid, p in self._profiles.items() if p.os == os]
        return list(self._profiles.keys())
