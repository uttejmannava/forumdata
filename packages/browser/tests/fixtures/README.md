# Browser Test Fixtures

This directory contains recorded browser interactions for reproducible testing.

## Recording New Fixtures

Use the `InteractionRecorder` to capture interactions against a live site:

```python
from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.testing.recorder import InteractionRecorder
from pathlib import Path

async def record():
    async with InteractionRecorder("my_fixture") as recorder:
        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=False)
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            recorder.attach(page)
            await page.goto("https://example.com/data")
            await recorder.capture_dom_snapshot(page)
        recorder.save(Path("tests/fixtures/my_fixture"))
```

## Replaying Fixtures in Tests

```python
from forum_browser.testing.recorder import InteractionRecorder
from forum_browser.testing.replay import InteractionReplayer

session = InteractionRecorder.load(Path("tests/fixtures/my_fixture"))
replayer = InteractionReplayer(session)

async with ForumBrowser(config) as browser:
    page = await browser.new_page()
    await replayer.install(page)
    await page.goto(session.target_url)
    # Page loads from recorded fixtures, no live network calls
```

## Existing Fixtures

- `simple_table/` — A simple HTML table with settlement prices (inline fixture, no live site needed)

## Guidelines

- Small fixtures (< 100KB) may be committed to the repo
- Large fixtures should be `.gitignore`d and regenerated as needed
- Always include a `recording.json` and optionally `dom_snapshot.html`
