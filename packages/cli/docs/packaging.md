# Packaging and releasing

How `example-cli` is built and published. The Windows and Linux installers are built from the same sources; their notes are linked below.

## What is built

| Output | Where it is described |
| --- | --- |
| The PyPI package `example-cli` (sdist and wheel) | this page |
| A Windows setup and zip, and Linux `.deb` and `.rpm` packages | [installer packaging](../../../installer/docs/packaging.md) |

`uv build --package example-cli` writes the sdist and wheel to `dist/`. The wheel holds `example_cli` only, and the `example-cli` console script. It depends on `example-package`, `typer` and `rich`, which pip or uv install with it.

## Versions

The version is `__version__` in `src/example_cli/__init__.py`, separate from the core library's. Follow [Semantic Versioning](https://semver.org/): commands, options, output formats and exit codes are the public interface. The history is [`CHANGELOG.md`](../CHANGELOG.md).

## Making a release

One-time set-up:

1. On PyPI, add a trusted publisher for `example-cli`: this repository, workflow `release.yml`, environment `cli`.
2. Create the GitHub environment `cli` (the settings script does, restricted to `cli-v*` tags).

Each release:

1. Release the core first if it changed, because the wheel depends on `example-package` on PyPI.
2. Bump `__version__`, update the [guide](guides/cli.md) if commands changed, and move `[Unreleased]` entries of `CHANGELOG.md` under a version heading, in a pull request.
3. Publish a GitHub release tagged `cli-v<version>` (for `0.2.0`, `cli-v0.2.0`).
4. `release.yml` checks the tag, builds, and publishes after the `cli` environment is approved. The files are attached with `SHA256SUMS.txt`, and `cli-latest` moves to the new version.

The installers have their own tag (`installer-v<version>`) and version, so you can ship a new setup without a PyPI release.

## Installing

```bash
uv tool install example-cli      # recommended: an isolated environment
pipx install example-cli
uvx --from example-cli example-cli --help   # one-off, no install
```
