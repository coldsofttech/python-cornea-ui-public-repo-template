# Installer packaging and releasing

How the installers are built and released: one Windows setup for the command line and the desktop window, a portable zip of the command line, and the command line's Linux packages. Everything is in the root `installer/` folder and `installer/scripts/build.py`. How releases are routed for every package is in the [project releasing notes](../../docs/releasing.md); the PyPI package of the command line is in the [CLI packaging notes](../../packages/cli/docs/packaging.md).

## What is built

| Where | What you get | Built with |
| --- | --- | --- |
| Windows | `example-<version>-full-setup.exe` (command line, window, or both), `example-<version>-components.json` and a portable command line zip `example-<cli version>-windows-x64.zip` | PyInstaller and NSIS |
| Linux | the command line as `.deb` and `.rpm`, for x86_64 and arm64 | PyInstaller and nfpm |
| macOS | no installer: install the PyPI package (`uv tool install example-cli`) | |

The window needs Windows, so Linux packages hold the command line only.

## Versions

The setup has its own version (`version` in `installer/build.toml`, history in [`installer/CHANGELOG.md`](../CHANGELOG.md)), tagged `installer-v<version>`. It is separate from the command line and the window it contains, so a fix in the command line (0.1.1) can ship in a new setup (0.1.1) while the window stays 0.1.0, and an installer-only fix can ship without touching either.

- Raise the setup version whenever a bundled program or the installer changes, by at least as much as the biggest change inside.
- Each setup records the versions it contains: in the registry (`CliVersion`, `UiVersion`) and in `example-<version>-components.json` beside it.
- The zip and the Linux packages carry the command line's own version.

## The files

```text
installer/
  build.toml                the setup's version, title, publisher and install folder
  CHANGELOG.md                the setup's history
  pyinstaller/example.spec     freezes both programs into one folder
  windows/setup.nsi           the Windows setup and uninstaller
  windows/path.ps1            the PATH edit, run by the setup
  linux/nfpm.yaml             the deb and rpm packages
  tools.toml                  pinned NSIS and nfpm versions
installer/scripts/build.py    the build: the programs (names, versions, what is frozen), PyInstaller
                              helpers, NSIS, the zip, nfpm, signing and branding
```

Names, version and description are never repeated. Executable names are the `[project.scripts]` and `[project.gui-scripts]` keys, the command line's version is `__version__`, the window's is `version` in its `pyproject.toml`, and the window's title is `TITLE` in `example_ui/app.py`; `build.toml` says where to read each. The `Product` classes in `build.py` read them (and `--github-env` exports them to CI), so renaming a program needs no edit in the installer.

## Building the installers

```bash
uv sync --group installer
uv run python installer/scripts/build.py --build-frontend --smoke     # Windows: setup and zip
uv run python installer/scripts/build.py --format deb,rpm --smoke     # Linux: the packages
```

On Windows `--build-frontend` runs `npm ci` and `npm run build` (Node as in `.nvmrc` of the window), and `--sync` runs `uv sync --all-packages --group installer` first. `--smoke` starts the built programs and checks they answer. A format the current OS cannot build (`deb` or `rpm` on Windows, `exe` on Linux) stops the build with an error. Results are in `dist/installer/` and the PyInstaller folder is in `build/installer/`.

| You need | For |
| --- | --- |
| `uv sync --group installer` | PyInstaller and the build backend |
| Node (see the window's `.nvmrc`) | the window's frontend (Windows) |
| NSIS (version in `installer/tools.toml`) | the Windows setup; `makensis` on `PATH` or in `Program Files (x86)\NSIS` |
| nfpm (version in `installer/tools.toml`) | the Linux packages; set `NFPM` to run it another way, for example `NFPM="uvx nfpm"` |

### PyInstaller

`example.spec` (which calls `Cli().program()` and `Ui().program()`) makes one one-folder build (no one-file build): `example.exe`, `example-ui.exe` (Windows only, no console) and one `lib/` folder. Each program carries its own Python modules; `lib/` holds the runtime and the native libraries and data. The entry scripts are generated from the `[project.scripts]` and `[project.gui-scripts]` targets, and the executables carry the icon and file properties taken from the projects. The window's built frontend is frozen into `lib/`.

The spec also writes `example-components.json`, the files of `lib/` that only one program needs. The build script uses it to split the folder into `core` (needed by both), `cli` and `ui` before the setup is built. On Linux only the command line is built.

The `*.dist-info` folders of the libraries are left out of `lib/`, because nothing reads them at run time. Their licence texts are gathered in `lib/THIRD_PARTY_LICENSES.txt`, so the libraries are still shipped with their licences. If a new dependency needs its metadata at run time (`importlib.metadata`), keep its `*.dist-info` in the `files()` function of `example.spec`.

### The settings in `build.toml`

`installer/build.toml` holds the product's identity and everything the build is told, so the build script has no project facts of its own. Package names, versions and entry points still come from the packages.

- **Identity:** `name` (file name stem), `version` (of the setup), `title`, `publisher`, `install-dir`, and `guid`, the product id passed to NSIS. Keep the GUID for the life of the project: it is how a newer setup replaces an older one.
- **`[licence]`:** `file` is shown by the setup, and `name` goes in the executables' file properties. **`[links]`:** `homepage`, `issues` and `changelog` appear in Apps & features and in the Linux packages.
- **`[build]`:** the PyInstaller spec, the NSIS script and the nfpm file, and `smoke-args`, the pytest options of `--smoke`. **`[formats]`:** what each OS builds (`windows`, `linux`), which `--format` chooses from.
- **`[brand]`:** the artwork, below.
- **`[[products]]`:** one entry per program, in order:
  - `name` (also the folder the setup stages it in), `type` (`cli` or `ui`: a `Product` class in `build.py`) and `path` of its package.
  - `title` and `version`. Each is a literal, `"pyproject"` (the package's `[project]` version) or a `{ file, pattern }` table: a file of the package and a regex whose first group is the value. The version stays defined in the code (`__version__`, `version` in `pyproject.toml`) and `build.toml` only says where.
  - `excludes` (left out of its build), `collect` (packages collected whole), `compile-pyc` (folders under `lib/` whose `.py` files are shipped as compiled `.pyc`, empty by default) and `smoke` (the integration test, run from its `path`, that `--smoke` uses).
  - Type-specific keys: `core-package` for `cli`; `api-package`, `frontend`, `frontend-build` and `frontend-dist` for `ui`. `--build-frontend` runs the `frontend-build` commands in the `frontend` folder; the `frontend-dist` folder (from there) must not be empty and is frozen at the same path under `src/`.

`compile-pyc` replaces each `.py` of the listed folders (for example `rich`) with a `.pyc` compiled by the build's Python, which is the frozen one, so the source is not shipped and the files are smaller. The `.pyc` sits where the source was and is imported without it. Only list a library that does not read its own source at run time (`inspect.getsource`, templates written as `.py`), and test the program after changing the list. Tracebacks show the file's place under `lib/` and no source lines for these files.

Add a library to `collect` when the built program fails with a missing module that is loaded by name; add it to `excludes` to keep it out of a program that does not need it (the command line leaves out the window's libraries). `--github-env` exports every product's names to CI.

To add a program of a new kind, such as a background service, add a `Product` subclass with a new `type` and an entry for it. The Windows setup (`setup.nsi`) still has its components written out for the command line and the window, so a new product also needs its section there.

### Brand files

The executables, the setup and the packages use artwork that `[brand]` in `installer/build.toml` names, as paths from the repository root. The build stops with a message when a named file is missing.

| Key | Used for | Size |
| --- | --- | --- |
| `icon` (required) | the Windows executables, the setup and the uninstaller icon (`.ico`) | 16 to 256 px |
| `png-dir` (required) | the folder with `app-16.png` to `app-256.png`, the icon in the Linux deb and rpm (hicolor icon theme) | 16, 24, 32, 48, 64, 128, 256 px |
| `header-image` (optional) | the Windows setup header | 150x57 |
| `welcome-image` (optional) | the Windows setup welcome and finish pages | 164x314 |

The bitmaps must be 24-bit BMP; when a key is left out, NSIS uses its default artwork.

## Windows setup

`setup.nsi` is one NSIS script for both programs.

- **Pages:** components (command line, window, or both; at least one) > folder > tasks (add the command line to `PATH`, desktop shortcut for the window). `PATH` applies only to the command line and the desktop shortcut only to the window, so each is greyed out when its program is not chosen.
- **Who it is for:** the default is a per-user install. The mode page offers all users, which asks for administrator rights.
- **Folder:** under `Program Files` (or `%LOCALAPPDATA%\Programs` for one user), from `install-dir` in `installer/build.toml`.
- **Start Menu:** a folder (`start-menu-dir` in `build.toml`, `Example App`; one level, because Windows 11 flattens nested Start folders) with a prompt where `example-cli` works even if it was not added to `PATH`, a shortcut to the window, and an uninstall shortcut. Each exists only for an installed program.
- **PATH:** edited through `path.ps1`, never with NSIS string functions, and removed again when the command line is removed.
- **Upgrades:** a newer setup with the same product id keeps the programs that are installed, adds the chosen ones and replaces `lib/` as a whole, so no stale files stay behind.

### The shared `lib/`

`lib/` is common to both programs. Setup always installs `core` and installs the command line's or the window's own files only when that program is chosen, so installing the command line alone leaves out the window's libraries. Which programs are installed is kept in the registry (`Software\Example App`, values `Cli` and `Ui`), so setup and the uninstaller always know what else uses `lib/`.

### Uninstall

The uninstaller (Settings > Apps, or `uninstall.exe`) lists only the installed programs, and either or both can be removed. Removing one deletes its executable, the library files only it needs, its shortcuts and, for the command line, its `PATH` entry. `lib/`, `uninstall.exe`, the Start Menu folder and the registry keys go only when neither program is left. It removes only what setup installed, so a folder chosen by hand keeps anything else in it.

### Silent use

For scripts and package managers:

```text
example-<version>-full-setup.exe /S [/allusers | /currentuser] [/COMPONENTS=cli|ui|cli,ui] [/NOPATH] [/DESKTOP] [/D=C:\folder]
uninstall.exe /S [/COMPONENTS=cli|ui|cli,ui]
```

`/D=` must come last. Without `/COMPONENTS`, both programs are installed (or removed). The product id (a GUID) in `setup.nsi` identifies the product for upgrades, so keep it for the life of the project. To make a new one, use `python -c "import uuid; print(uuid.uuid4())"`. The earlier separate command line and window setups are not upgraded by this one: remove them first.

Windows may refuse to start a freshly built, unsigned program (Smart App Control or application control returns error 4551). The smoke tests skip in that case. Signing removes the problem (see [Signing](#signing)); without it, users also see SmartScreen warnings.

### WebView2

The window uses the Microsoft Edge WebView2 runtime, already part of Windows 10 and 11. The installer does not add it; `cornea doctor` checks for it.

## Linux

`nfpm.yaml` builds one package from the PyInstaller folder, as a `.deb` and a `.rpm`, for x86_64 and arm64. It installs the folder under `/usr/lib/<name>/`, links the command into `/usr/bin`, puts the license in `/usr/share/doc/<name>/` and the icons in `/usr/share/icons/hicolor/<size>/apps/`. The only dependency is the C library (`libc6`, or `glibc` on rpm), since PyInstaller bundles the rest.

- Packages are system-wide, need root and are not signed. Removing one deletes only its own files and never touches a user's home.
- The build script sets file modes (folders 755, files 644, executables 755) before packaging.
- Values such as the name, version, architecture, description and maintainer come from the environment that `installer/scripts/build.py` sets from `pyproject.toml`. The maintainer needs an email in the author, which Debian expects.
- Each package is built on a runner of its own architecture, so the arm64 package is built on an arm64 runner.

| Distribution | Install | Remove |
| --- | --- | --- |
| Debian, Ubuntu | `sudo apt install ./example_<version>_amd64.deb` (or `_arm64.deb` on ARM) | `sudo apt remove example` |
| Fedora, RHEL | `sudo dnf install ./example-<version>-1.x86_64.rpm` (or `.aarch64.rpm` on ARM) | `sudo dnf remove example` |

## Checks

- `packages/cli/tests/integration/test_frozen_cli.py` and `packages/ui/tests/integration/test_frozen_ui.py` start the built programs and check they answer. They are skipped when there is no build.
- The `ui-installer` job in `ci-ui.yml` builds the full setup and the zip on Windows, then runs `.github/actions/test-windows-installer`: it installs the command line alone, adds the window, removes the window while checking the command line still works, then removes the rest and checks nothing is left (including `lib/` and `PATH`).
- The `cli-installer` job in `ci-cli.yml` builds the Linux packages on x86_64 and arm64, starts the frozen program, then installs it with `apt` and, for the rpm, in a Fedora container, including the icon.

## Making a release

1. Bump `version` in `installer/build.toml` and move the `[Unreleased]` entries in `installer/CHANGELOG.md` under a `## [x.y.z]` heading, listing the command line and window versions inside. The programs' own versions and changelogs are bumped in their packages.
2. Merge that pull request, then publish a GitHub release tagged `installer-v<version>`.
3. `release.yml` calls `release-installer.yml`, which does the rest:

| Step | Result |
| --- | --- |
| Check | the tag must be `installer-v` plus the version in `installer/build.toml` |
| Installer | the Windows setup, `components.json` and the zip, and the Linux deb and rpm packages (x86_64 and arm64), are built and smoke tested; the Windows files are signed when a signing command is set |
| Approval | the job waits for a reviewer of the `installer` environment |
| Publish | the files and `SHA256SUMS.txt` are attached to the GitHub release |

Everything is built and tested before the approval. Nothing is published to PyPI.

To check a download: `sha256sum --check SHA256SUMS.txt` (Linux), or `Get-FileHash <file>` on Windows and compare with the list.

### Build time

Starting targets, to be revisited after the first real runs and recorded here:

| Job | Target | `timeout-minutes` |
| --- | --- | --- |
| Windows installer | under 10 minutes | 30 |
| Linux packages | under 5 minutes | 15 |

A job that passes its timeout fails instead of hanging. uv caches keep builds inside the targets.

## Signing

Signing is off by default. It applies to the Windows programs only; Linux packages are not signed.

To turn it on, set the repository variable `SIGN_COMMAND` to a command that signs one file, with `{file}` where the path goes. The build signs the executables first, then the `setup.exe`, so the files inside the installer are signed too. Any provider works, since the command is yours. Examples of what exists, without a recommendation:

- SignPath (free for qualifying open-source projects)
- Azure Trusted Signing (paid subscription)
- a certificate from a certificate authority, on a hardware token or in a cloud HSM

Secrets the command needs (a token, a certificate password) are added as repository secrets and passed to the step that builds the installer through `env` in `release-installer.yml`, which is the one place to edit (and `release-cli.yml` for the Linux job).

## Package managers

Homebrew, Scoop and winget are not updated by the workflows for now. The Scoop manifest installs the command line zip, which is attached to the `installer-v<version>` release.

## Before the first release

- Check that the product id (GUID) in `installer/windows/setup.nsi` is the one you want to keep for good.
- Pin the NSIS and nfpm versions in `installer/tools.toml`.
- Add an email to the author in `packages/cli/pyproject.toml`, which Debian expects in the maintainer field.
- Create the `installer` environment with its reviewers.
- Decide on signing.
