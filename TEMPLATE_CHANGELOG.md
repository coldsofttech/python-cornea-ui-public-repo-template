# Template changelog

Changes to the template itself. This file is removed when you initialise a repository from the template; your own history belongs in `CHANGELOG.md`.

## [Unreleased]

### Added

- Optional `publisher` setting for the name shown in Add/Remove Programs and the file properties, and an optional `--publisher` for the init script.

### Changed

- Smaller installers: dev tools and unneeded package metadata are left out.
- Setups are named `<name>-cli-<version>.setup.exe` and `<name>-<version>.setup.exe`.
- The window is shipped only in the UI installer.
- Both installers share one Start Menu folder, with one shortcut per product.
- Installer pages use the brand art, and the build gained a `--sync` option.

### Fixed

- The installer no longer bundles library `.py` files as data.
- Building the installer for a single product now works.

### Removed

- Claude Code configuration and instructions.

## 2026-11-08

### Changed

- Updated the `oasdiff` GitHub Action used to check API changes.

## 2026-11-01

### Added

- The API, window and installer layers.

### Changed

- Updated `@testing-library/jest-dom` in the window's frontend.
