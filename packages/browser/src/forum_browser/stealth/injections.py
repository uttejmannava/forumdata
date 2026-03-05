"""Browser-side injection scripts for anti-fingerprinting."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

    from forum_browser.stealth.profiles import DeviceProfile

# JavaScript injection that overrides canvas and WebGL APIs to add deterministic noise
# seeded by the profile's canvas_noise_seed. This ensures fingerprints are consistent
# within a session but unique across profiles.
_CANVAS_WEBGL_NOISE_SCRIPT = """
(profile) => {
    // Seeded PRNG (mulberry32)
    function mulberry32(a) {
        return function() {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        }
    }
    const rng = mulberry32(profile.canvas_noise_seed);

    // Canvas 2D noise injection
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                // Add +-1 noise to RGB channels
                imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (rng() > 0.5 ? 1 : -1)));
                imageData.data[i+1] = Math.max(0, Math.min(255, imageData.data[i+1] + (rng() > 0.5 ? 1 : -1)));
                imageData.data[i+2] = Math.max(0, Math.min(255, imageData.data[i+2] + (rng() > 0.5 ? 1 : -1)));
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return origToDataURL.call(this, type, quality);
    };

    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
        // Apply noise via the same ImageData manipulation as toDataURL,
        // then delegate to the original toBlob implementation.
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (rng() > 0.5 ? 1 : -1)));
                imageData.data[i+1] = Math.max(0, Math.min(255, imageData.data[i+1] + (rng() > 0.5 ? 1 : -1)));
                imageData.data[i+2] = Math.max(0, Math.min(255, imageData.data[i+2] + (rng() > 0.5 ? 1 : -1)));
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return origToBlob.call(this, callback, type, quality);
    };

    // WebGL parameter overrides
    const origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        const UNMASKED_VENDOR = 0x9245;
        const UNMASKED_RENDERER = 0x9246;
        if (param === UNMASKED_VENDOR) return profile.webgl_vendor;
        if (param === UNMASKED_RENDERER) return profile.webgl_renderer;
        return origGetParameter.call(this, param);
    };

    if (typeof WebGL2RenderingContext !== 'undefined') {
        const origGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {
            const UNMASKED_VENDOR = 0x9245;
            const UNMASKED_RENDERER = 0x9246;
            if (param === UNMASKED_VENDOR) return profile.webgl_vendor;
            if (param === UNMASKED_RENDERER) return profile.webgl_renderer;
            return origGetParameter2.call(this, param);
        };
    }

    // Navigator overrides
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => profile.hardware_concurrency});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => profile.device_memory});
    Object.defineProperty(navigator, 'platform', {get: () => profile.platform});

    // Screen property overrides
    if (profile.screen_width) {
        Object.defineProperty(screen, 'width', {get: () => profile.screen_width});
        Object.defineProperty(screen, 'height', {get: () => profile.screen_height});
        Object.defineProperty(screen, 'availWidth', {get: () => profile.screen_width});
        Object.defineProperty(screen, 'availHeight', {get: () => profile.screen_height});
    }
    if (profile.device_pixel_ratio) {
        Object.defineProperty(window, 'devicePixelRatio', {get: () => profile.device_pixel_ratio});
    }

    // Font enumeration spoofing — override document.fonts.check() to only
    // report fonts that appear in the profile's font list.
    if (profile.fonts && profile.fonts.length > 0 && document.fonts) {
        const allowedFonts = new Set(profile.fonts.map(f => f.toLowerCase()));
        const origCheck = document.fonts.check.bind(document.fonts);
        document.fonts.check = function(font, text) {
            // Extract font family from the CSS font shorthand (e.g. "12px Arial")
            const parts = font.split(/\\s+/);
            const family = parts.slice(1).join(' ').replace(/['"]/g, '').toLowerCase();
            if (family && !allowedFonts.has(family)) return false;
            return origCheck(font, text);
        };
    }
}
"""


async def inject_fingerprint_overrides(context: BrowserContext, profile: DeviceProfile) -> None:
    """Inject canvas/WebGL noise and navigator overrides into all pages in a context.

    Must be called before navigating to any pages. Uses add_init_script to ensure
    the overrides are applied before any page JavaScript runs.
    """
    import json

    profile_json = json.dumps({
        "canvas_noise_seed": profile.canvas_noise_seed,
        "webgl_vendor": profile.webgl_vendor,
        "webgl_renderer": profile.webgl_renderer,
        "hardware_concurrency": profile.hardware_concurrency,
        "device_memory": profile.device_memory,
        "platform": profile.platform,
        "screen_width": profile.screen_width,
        "screen_height": profile.screen_height,
        "device_pixel_ratio": profile.device_pixel_ratio,
        "fonts": list(profile.fonts),
    })
    # Wrap the IIFE to pass the profile data as a JSON literal
    script = f"({_CANVAS_WEBGL_NOISE_SCRIPT})({profile_json})"
    await context.add_init_script(script)
