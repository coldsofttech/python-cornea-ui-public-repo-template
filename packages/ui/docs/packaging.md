# Packaging and releasing

How `example-ui` reaches users. The window is not published to PyPI: the Windows setup carries it, together with the command line.

## What is built

The window is frozen by PyInstaller into the same one-folder build as the command line (`example-ui.exe`, no console, next to `example-cli.exe` and a shared `lib/`), and NSIS wraps it in `example-<version>-full-setup.exe` (the command line, the window, or both). The frontend's `dist/` is frozen into the build at the path the app expects, so users need no Node. Everything about the build, signing and the setup's options is in [installer packaging](../../../installer/docs/packaging.md).

## Versions

The window has its own version, `version` in `packages/ui/pyproject.toml` (the title is `TITLE` in `example_ui/app.py`). The setup has another, in `installer/build.toml`, and each setup records the versions it contains. History is in [`CHANGELOG.md`](../CHANGELOG.md).

## Releasing

A window release is an installer release: bump the window's version (and the setup's), update both changelogs, and publish a GitHub release tagged `installer-v<version>`. The `Release installer` workflow builds the frontend, freezes the programs on Windows, optionally signs them (`SIGN_COMMAND`), and attaches the files after the `installer` environment is approved. See [releasing](../../../docs/releasing.md).

## From the source tree

```bash
uv sync
npm ci --prefix packages/ui/src/example_ui/ui && npm run build --prefix packages/ui/src/example_ui/ui
uv run python installer/scripts/build.py --smoke    # Windows: setup and zip
```
