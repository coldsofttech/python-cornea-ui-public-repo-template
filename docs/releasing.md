# Releasing

How a release is routed. Each package's packaging notes hold the steps and set-up for its own release: [core](../packages/core/docs/packaging.md#releasing-to-pypi), [command line](../packages/cli/docs/packaging.md#making-a-release), [window](../packages/ui/docs/packaging.md) and [installers](../installer/docs/packaging.md#releasing).

## Releases are routed by tag

Publishing a GitHub release runs `release.yml`, and the tag decides what is released. Each part has its own workflow, its own version and its own approval: the job that publishes waits for a reviewer of its environment (Settings > Environments), after everything has been built and tested.

| Tag | Releases | Environment |
| --- | --- | --- |
| `v<version>` | the core library, `example-package`, on PyPI | `core` |
| `cli-v<version>` | the command line, `example-cli`, on PyPI | `cli` |
| `installer-v<version>` | the Windows setup (command line and window) and portable zip, and the Linux deb and rpm packages; version in `installer/build.toml` | `installer` |

The API and the window are not published to PyPI: they ship inside the installer. The tag must equal the version of the package it releases (`installer/build.toml` for the installers). Release the core before the command line, because `example-cli` depends on the `example-package` package on PyPI. Every release that attaches files also gets `SHA256SUMS.txt`.

Before releasing, bump the package's version and move its `[Unreleased]` changelog entries under a version heading. The root [`CHANGELOG.md`](../CHANGELOG.md) covers the repository as a whole.

## Latest markers

GitHub allows one Latest release per repository, so the core owns the badge: after every full release the newest `v<version>` release is marked Latest. Each package also gets its own pointer, a tag and pre-release named `<package>-latest` (`core-latest`, `cli-latest`, `installer-latest`) that moves to the newest version and carries its files. Pre-releases change no marker.

## Signing

The installers are signed only when the repository variable `SIGN_COMMAND` is set to a command that signs one file, with `{file}` where its path goes. The build signs the executables first, then the setup. Any provider works, since the command is yours (SignPath, Azure Trusted Signing, a certificate on a hardware token or in a cloud HSM); secrets it needs are repository secrets passed through `env` in `release-installer.yml`. Without signing, Windows shows SmartScreen warnings. Linux packages are not signed. The `publisher` in `installer/build.toml` only fills in Add/Remove Programs and the file properties; the publisher on the UAC prompt comes from the certificate.

## Build time

Starting targets, to be revisited after the first real runs: the Windows installer under 10 minutes (timeout 30), the Linux packages under 5 minutes (timeout 15). A job that passes its timeout fails instead of hanging.

## One-time set-up

1. Run `scripts/apply_repo_settings.py` to create the three environments, restricted to their tag patterns, and the branch ruleset.
2. Add required reviewers to each environment you want an approval step for.
3. On PyPI, add a trusted publisher for each published project: workflow `release.yml`, environment `core` or `cli`.
4. Optionally set `SIGN_COMMAND`.

Homebrew, Scoop and winget are not updated by the workflows; add jobs to `release.yml` when you want them.
