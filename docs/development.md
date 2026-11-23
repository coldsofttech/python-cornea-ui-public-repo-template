# Development

Repository-wide tooling and workflow. Each package has its own guide with the commands for that package: [core](../packages/core/docs/development.md), [command line](../packages/cli/docs/development.md), [API](../packages/api/docs/development.md) and [window](../packages/ui/docs/development.md). The container image is described in [`packages/docker/docs`](../packages/docker/docs/docker.md).

## Layout

```text
packages/core/         example-package: the library, all the logic, never prints or exits (typed)
packages/cli/          example-cli: Typer + Rich command line over the library
packages/api/          example-api: FastAPI app over the library (not published to PyPI)
packages/ui/           example-ui: Cornea Shell window and the React frontend (not published to PyPI)
packages/docker/       Dockerfile, image tests and docs of the container image (core and cli)
packages/*/src/        each package's source; packages/*/tests/ has unit/ and integration/
packages/*/docs/       each package's documentation
installer/             the Windows setup, Linux packages and the PyInstaller build (see installer/docs/packaging.md)
brand/                 sample icon and setup artwork used by the installers
scripts/               repository settings and the Init rename script
docs/                  repository-wide documentation
pyproject.toml         uv workspace root: dev dependencies and shared tool configuration
uv.lock                locked dependencies (commit this file)
```

The example names are `example_package` (library), `example_cli` (command line package), `example_api`, `example_ui`, and the commands `example-cli` and `example-ui`. After creating a repo from this template, run the **Init** workflow with a short lowercase `name` (for example `acme`) and a display `title` (for example "Acme Studio"). It opens a pull request that:

- replaces the owner and repository name;
- renames the packages (`acme_package`, `acme_cli`, `acme_api`, `acme_ui`), the commands (`acme-cli`, `acme-ui`), the settings prefix (`ACME_API_`) and the app id, and replaces "Example App" with your title;
- generates a new product GUID for the Windows setup (`installer/build.toml`), then regenerates `uv.lock` and `packages/api/docs/openapi.json`.

The rename is `scripts/init_template.py` (it replaces only those exact patterns, so prose such as "for example" is left alone, and it deletes itself afterwards, along with `TEMPLATE_CHANGELOG.md`, which records the template's own changes and is not meant for your repository). The workflows and the installer scripts read names from each package's `pyproject.toml` and `installer/build.toml`, so they need no renaming. If you add a new place that uses an example name, keep it in one of the patterns the script knows.

What is left for you:

1. Replace the window icon (`packages/ui/src/<ui package>/ui/public/icon.png`) and the artwork in `brand/`.
2. Set the descriptions and URLs, and add an email to the author, in each package's `pyproject.toml` and in `installer/build.toml`.
3. Review the pull request for lines that still say "example" (the script lists them).
4. Replace the example React app, API routes and window action.

See [installer packaging](../installer/docs/packaging.md) and [releasing](releasing.md) for the installers and the first-release checklist. Commands, options and exit codes are in the [command line guide](../packages/cli/docs/guides/cli.md).

## Tooling

| Purpose | Tool |
| --- | --- |
| Environment, dependencies, build | [uv](https://docs.astral.sh/uv/) with Hatchling |
| Lint and format | Ruff |
| Type checking | mypy (strict) |
| Tests and coverage | pytest with pytest-cov (80% minimum) |
| API | FastAPI, uvicorn, pydantic-settings; Schemathesis for contract tests |
| Window | `cornea-shell` (Windows only) |
| Frontend | Node 22 or newer, Vite, React, Vitest, ESLint, Prettier |

```bash
uv sync --all-packages                       # create .venv and install every package and the dev tools
uv run pytest packages/core/tests            # unit tests of one package, with coverage (skips integration tests)
uv run pytest -m integration packages/api/tests --no-cov   # integration tests of one package
uv run ruff check .                          # lint
uv run ruff format .                         # format
uv run mypy                                  # type check
uv build --package example-cli               # build the sdist and wheel of a published package
```

Frontend, from `packages/ui/src/example_ui/ui` (or with `--prefix`):

```bash
npm ci                     # install exactly what package-lock.json says
npm run dev                # Vite dev server; `uv run python -m example_ui --dev` wraps it in the window
npm run build              # writes dist/, which the window serves and the Windows installer freezes in
npm run lint && npm test   # ESLint, Vitest
npm run format             # Prettier
```

Other useful commands:

```bash
uv run python -m example_api                              # run the API on its own
uv run python packages/api/scripts/export_openapi.py      # regenerate packages/api/docs/openapi.json
uv run python -m example_ui --no-window                   # serve the UI for a browser
uv run python installer/scripts/build.py --smoke          # build the installers for this OS
```

## Integration tests

Each package has `tests/unit/` and `tests/integration/`; tests in an `integration` folder are marked `integration` automatically by the package's `conftest.py`. They are excluded from the default `pytest` run, and therefore from the pre-commit hook, and run as their own jobs in CI. Run one package at a time (the `tests` folders share a name), for example `uv run pytest packages/api/tests --no-cov -m integration`. They include a real API server, a Schemathesis contract test and, on Windows with a built frontend, a real Cornea server without a window.

## Continuous integration

The `ci` workflow calls one workflow per package (`ci-core`, `ci-cli`, `ci-api`, `ci-ui`, `ci-docker`), one for the rest of the repository (`ci-repo`) and `ci-installer` once the cli and ui checks pass. On pull requests, `changes.yml` runs only the parts a change can affect (`api` and `ui` follow `core`; `docker` follows `core` and `cli`; `installer` follows `cli` and `ui`). A final `ci` job gates on all of them and is the single required check in the branch ruleset. Shared steps live in `.github/actions/`. `audit`, `security` and `api-compat` are separate workflows; see [architecture](architecture.md#workflows).

## Releasing

The routing of tags to packages, signing and the one-time set-up are in [releasing](releasing.md); the steps for each package are in its packaging notes.
