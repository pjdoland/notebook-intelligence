# UI tests

Galata-based Playwright tests that drive a real JupyterLab instance with the
notebook-intelligence labextension installed. The suite is intentionally small
— a smoke test that the extension activates and that the chat sidebar opens —
and exists primarily as a scaffold so further UI tests can be added without
re-bootstrapping the harness.

## Running locally

From the repository root:

```bash
# Install the extension into the dev environment first.
pip install -e .[test]
jlpm
jlpm build

# Install ui-tests dependencies and Playwright browsers.
cd ui-tests
jlpm
jlpm playwright install chromium

# Run the suite.
jlpm test
```

`jlpm test:debug` opens the Playwright inspector for stepwise debugging;
`jlpm test:update` regenerates snapshots when an intentional UI change makes
the existing reference image stale.

## Layout

- `playwright.config.ts` — boots `jupyter lab` via `webServer`, points
  Playwright at `http://localhost:8888/lab`, enables traces + videos on
  failure, and retries twice on CI.
- `jupyter_server_test_config.py` — disables auth/XSRF and pins the port so
  Playwright connects deterministically.
- `tests/` — `*.spec.ts` files. Galata's `test`/`expect` come from
  `@jupyterlab/galata` and provide a `page` fixture that's already inside the
  lab shell.

## Adding tests

Each spec file is independent. Use Galata's [helpers](https://github.com/jupyterlab/jupyterlab/tree/main/galata)
(notebook commands, file browser, settings) before reaching for raw
`page.locator` so tests stay resilient to lab-side DOM changes.
