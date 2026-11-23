# Development

Working on `example-api` (`packages/api`). Repository-wide tooling is in the [root development guide](../../../docs/development.md).

## Layout

```text
src/example_api/       the app: main, config, auth, security, errors, logs, schemas, routers/
tests/unit/            route and middleware tests with FastAPI's TestClient
tests/integration/     tests of the running server and the OpenAPI contract
scripts/               export_openapi.py: writes docs/openapi.json
docs/                  this documentation, api.md and the generated openapi.json
.env.example           the settings, with safe example values
pyproject.toml         metadata, dependencies and the package's tool configuration
```

## Setup

From the repository root:

```bash
uv sync
cp packages/api/.env.example .env      # set EXAMPLE_API_API_KEYS, or EXAMPLE_API_AUTH_MODE=none for local work
uv run python -m example_api           # http://127.0.0.1:8000
```

The interactive docs (`/docs`) are on only with `EXAMPLE_API_DOCS_ENABLED=true`.

## Everyday commands

Run these from the repository root.

```bash
uv run pytest packages/api/tests                          # unit tests with coverage (80% minimum)
uv run pytest -m integration packages/api/tests --no-cov  # server and contract tests
uv run ruff check packages/api
uv run mypy packages/api/src
uv run python packages/api/scripts/export_openapi.py      # regenerate docs/openapi.json
```

## Tests

- `tests/conftest.py` gives every test fresh settings and an empty greeting store, with authentication off. Tests that check authentication set the environment themselves.
- **Integration tests** start the real server in a subprocess on a free port (`python -m example_api`) and check `/health`. The contract test fuzzes the running server against its own OpenAPI document with [Schemathesis](https://schemathesis.readthedocs.io/).

## Continuous integration

`ci-api.yml` runs `api-lint` (Ruff, mypy, pre-commit, and a check that regenerating `openapi.json` gives no difference), `api-test`, `api-int-test` and `api-build` (builds the wheel and checks it holds the API only). `api-compat.yml` compares `openapi.json` with the base branch and fails on breaking changes; it is not a required check, so a deliberate break can be merged knowingly.

## Before you open a pull request

1. Tests, lint and types pass, and `openapi.json` is regenerated.
2. The change is in the [API guide](api.md) and under `[Unreleased]` in [`CHANGELOG.md`](../CHANGELOG.md).
3. A breaking change is in a new version router, not in `/api/v1`.
