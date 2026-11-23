# Development

Working on `example-ui` (`packages/ui`). Repository-wide tooling is in the [root development guide](../../../docs/development.md). The window runs on Windows only; the Python tests also run on Linux and macOS because they replace Cornea's `Shell`.

## Layout

```text
src/example_ui/        __main__.py (the command), app.py (Cornea wiring)
src/example_ui/ui/     the frontend: src/, index.html, package.json, vite.config.js, tests; dist/ is built
tests/unit/            tests of the command and the wiring, with a fake Shell
tests/integration/     Windows-only tests: the real server without a window, and the built program
docs/                  this documentation and the window guide
pyproject.toml         metadata, dependencies and the package's tool configuration
```

## Setup

```bash
uv sync
npm ci --prefix packages/ui/src/example_ui/ui     # Node as in packages/ui/src/example_ui/ui/.nvmrc
npm run build --prefix packages/ui/src/example_ui/ui
uv run python -m example_ui                       # the window (Windows)
uv run python -m example_ui --no-window           # prints an address for a browser
uv run python -m example_ui --dev                 # Vite with hot reload
```

## Everyday commands

Run these from the repository root.

```bash
uv run pytest packages/ui/tests                          # unit tests with coverage (80% minimum)
uv run pytest -m integration packages/ui/tests --no-cov  # Windows: server and built-program tests
uv run ruff check packages/ui
uv run mypy packages/ui/src
npm --prefix packages/ui/src/example_ui/ui run lint      # ESLint
npm --prefix packages/ui/src/example_ui/ui run format:check
npm --prefix packages/ui/src/example_ui/ui test          # Vitest, Testing Library and an accessibility check
```

## Continuous integration

`ci-ui.yml` runs `ui-lint` (Ruff, mypy, pre-commit), `ui-lint-npm` (ESLint and Prettier), `ui-test` (Python unit tests), `ui-test-npm` (Vitest) and the integration jobs, including the Windows window test against a built `dist`. The built frontend is passed to `ci-installer.yml`, which freezes it into the installer. `npm audit` runs in `audit-ui.yml`.

## Before you open a pull request

1. Python and frontend tests, lint and types pass.
2. A new action or setting is in the [window guide](guides/ui.md) and under `[Unreleased]` in [`CHANGELOG.md`](../CHANGELOG.md).
3. The frontend still builds without inline scripts or styles, which Cornea's content security policy forbids.
