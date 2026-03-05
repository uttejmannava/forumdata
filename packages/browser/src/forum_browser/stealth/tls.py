"""TLS fingerprint management — ensure TLS client hello matches the claimed browser/OS."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forum_browser.stealth.profiles import DeviceProfile


def get_browser_args_for_profile(profile: DeviceProfile) -> list[str]:
    """Return Chromium launch args that match the profile's TLS expectations."""
    args: list[str] = [
        "--disable-blink-features=AutomationControlled",
        f"--lang={profile.locale}",
    ]
    if profile.browser == "chrome":
        args.extend([
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--disable-features=IsolateOrigins,site-per-process",
        ])
    return args


def get_impersonation_for_profile(profile: DeviceProfile) -> str:
    """Map a device profile to the appropriate curl_cffi impersonation target."""
    browser = profile.browser.lower()
    if browser == "chrome":
        return "chrome"
    if browser == "firefox":
        return "firefox"
    if browser == "safari":
        return "safari"
    if browser == "edge":
        return "edge"
    return "chrome"
