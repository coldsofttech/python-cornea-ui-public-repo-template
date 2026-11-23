#!/usr/bin/env python3
"""Build the installers: one Windows setup with the command line and the window, and Linux packages.

    uv sync --group installer
    uv run python installer/scripts/build.py [--sync] [--build-frontend] [--smoke]
    (also: --format exe,deb,rpm)

On Windows it writes example-<version>-full-setup.exe (the command line, the window, or both, with
their shared lib/ folder), a components.json that says which versions are inside, and the
command line's portable zip. On Linux it writes the command
line's deb and rpm. Everything comes from the products' own metadata (the packages'
pyproject.toml files and installer/build.toml), so renaming a product needs no edit here.
Icon and setup art are named in installer/build.toml. Tool versions are pinned in
installer/tools.toml. The installers are written to dist/installer/. See docs/packaging.md.

Signing is off by default. Set SIGN_COMMAND to a command that signs one file, with {file} where
its path goes (for example a signtool or SignPath call); the executables and then the setup.exe
are signed. Nothing in this script is tied to one provider.
"""

import argparse
import functools
import importlib.util
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tomllib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, TypeVar

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "installer"
BUILD = ROOT / "build" / "installer"
WORK = ROOT / "build" / "installer-work"
OUT = ROOT / "dist" / "installer"
WINDOWS = sys.platform == "win32"
LINUX = sys.platform.startswith("linux")
T = TypeVar("T")


# ---- the programs: names and versions from each pyproject.toml, and what PyInstaller freezes ---
class Collected:
    """Data files, native libraries and hidden imports gathered for one executable."""

    def __init__(self) -> None:
        self.datas: list[Any] = []
        self.binaries: list[Any] = []
        self.hiddenimports: list[str] = []

    def package(self, name: str) -> None:
        """Collect a package whole: code, data files, native libraries and submodules."""
        from PyInstaller.utils.hooks import collect_all

        if importlib.util.find_spec(name) is None:
            return
        datas, binaries, hidden = collect_all(name)
        self.datas.extend(datas)
        self.binaries.extend(binaries)
        self.hiddenimports.extend(hidden)

    def metadata(self, *distributions: str) -> None:
        """Keep the package metadata that ``importlib.metadata`` reads at run time."""
        from PyInstaller.utils.hooks import copy_metadata

        for distribution in distributions:
            self.datas.extend(copy_metadata(distribution))


class Product:
    """One program of Example App: its ``[[products]]`` entry in build.toml and its pyproject.toml.

    A subclass says where its executable is declared (``scripts_key``) and whether it has a
    console (``console``), and fills in ``values()`` and ``dependencies()``. The title and version
    are resolved from build.toml (see ``resolve``). Renaming a program needs no edit here: the
    executable is the one key of ``[project.scripts]`` or ``[project.gui-scripts]``.
    """

    kind: ClassVar[str]  # the ``type`` of its [[products]] entry in installer/build.toml
    scripts_key: ClassVar[str]
    console: ClassVar[bool]
    windows_only: ClassVar[bool] = False

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.name: str = config["name"]
        self.directory = ROOT / config["path"]
        pyproject = self.directory / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        self.project: dict[str, Any] = data["project"]
        scripts: dict[str, str] = self.project.get(self.scripts_key, {})
        if len(scripts) != 1:
            raise SystemExit(f"{pyproject} needs exactly one [project.{self.scripts_key}] entry.")
        ((self.script, self.entry_point),) = scripts.items()
        self.module = self.entry_point.split(":")[0]
        self.package = self.module.split(".")[0]
        self.excludes: list[str] = config.get("excludes", [])
        self.collect: list[str] = config.get("collect", [])
        self.compile_pyc: list[str] = config.get("compile-pyc", [])
        self.smoke: str | None = config.get("smoke")
        self.frontend: Path | None = (
            self.directory / config["frontend"] if "frontend" in config else None
        )
        self.frontend_build: list[str] = config.get("frontend-build", [])
        self.frontend_dist: str = config.get("frontend-dist", "dist")
        self.title = self.resolve("title")
        self.version = self.resolve("version", "pyproject")

    def require(self, key: str) -> Any:
        """The value of ``key`` in the product's build.toml entry, or an error that names it."""
        if key not in self.config:
            raise SystemExit(f"Product {self.name} in build.toml needs {key}.")
        return self.config[key]

    def resolve(self, key: str, default: str | None = None) -> str:
        """A value kept in the code: a literal, ``"pyproject"`` (``[project] version``), or a
        ``{file, pattern}`` table (a file of the package and a regex whose first group is it)."""
        value = self.config.get(key, default)
        if value is None:
            raise SystemExit(f"Product {self.name} in build.toml needs {key}.")
        if isinstance(value, str):
            return str(self.project[key]) if value == "pyproject" else value
        path = self.directory / value["file"]
        match = re.search(value["pattern"], path.read_text(encoding="utf-8"), re.MULTILINE)
        if not match:
            raise SystemExit(f"{key} of product {self.name} not found in {path}")
        return match.group(1)

    def values(self) -> dict[str, str]:
        """The names the CI steps need, as environment variables."""
        raise NotImplementedError

    def dependencies(self) -> Collected:
        """What the program needs frozen in."""
        raise NotImplementedError

    def compile_sources(self, datas: list[Any]) -> list[Any]:
        """Ship the ``.py`` data files of the ``compile-pyc`` folders as compiled ``.pyc`` files.

        The folders are paths under ``lib/``. A ``.pyc`` next to where its source was is imported
        without the source. It is compiled with the Python that runs the build, which is the one
        that is frozen, and does not check the source's timestamp. The source's path is replaced
        by the file's place in ``lib/``, so tracebacks do not show the build machine's folders.
        """
        if not self.compile_pyc:
            return datas
        import py_compile

        from PyInstaller.config import CONF

        folders = tuple(f"{folder.strip('/')}/" for folder in self.compile_pyc)
        out = Path(CONF["workpath"]) / "pyc"
        converted: list[Any] = []
        for entry in datas:
            dest = entry[0].replace("\\", "/")
            if not (dest.endswith(".py") and dest.startswith(folders)):
                converted.append(entry)
                continue
            target = out / f"{dest}c"
            target.parent.mkdir(parents=True, exist_ok=True)
            py_compile.compile(
                entry[1],
                cfile=str(target),
                dfile=dest,
                doraise=True,
                invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
            )
            converted.append((f"{dest}c", str(target), entry[2]))
        return converted

    def build_frontend(self) -> None:
        """Run the product's ``frontend-build`` commands in its frontend folder."""
        if self.frontend is None:
            return
        for command in self.frontend_build:
            parts = shlex.split(command)
            parts[0] = shutil.which(parts[0]) or parts[0]  # npm.cmd on Windows
            run(parts, cwd=self.frontend)

    def entry_script(self) -> str:
        """Write the small script PyInstaller freezes for the program's entry point."""
        from PyInstaller.config import CONF

        function = self.entry_point.split(":")[1]
        path = Path(CONF["workpath"]) / f"entry_{self.script}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import multiprocessing\n"
            f"from {self.module} import {function}\n\n"
            'if __name__ == "__main__":\n'
            "    multiprocessing.freeze_support()\n"
            f"    raise SystemExit({function}())\n",
            encoding="utf-8",
        )
        return str(path)

    def version_info(self) -> Any:
        """Windows file properties (Explorer > Properties > Details) from build.toml."""
        from PyInstaller.utils.win32.versioninfo import (
            FixedFileInfo,
            StringFileInfo,
            StringStruct,
            StringTable,
            VarFileInfo,
            VarStruct,
            VSVersionInfo,
        )

        numbers = [int(n) for n in re.findall(r"\d+", self.version)[:4]]
        version = tuple(numbers + [0] * (4 - len(numbers)))
        settings = build_settings()
        publisher = settings["publisher"]
        strings = {
            "CompanyName": publisher,
            "FileDescription": self.project.get("description", self.title),
            "FileVersion": self.version,
            "ProductName": self.title,
            "ProductVersion": self.version,
            "LegalCopyright": f"{settings['licence']['name']}. {publisher}",
        }
        return VSVersionInfo(
            ffi=FixedFileInfo(
                filevers=version,
                prodvers=version,
                mask=0x3F,
                flags=0x0,
                OS=0x40004,
                fileType=0x1,
                subtype=0x0,
                date=(0, 0),
            ),
            kids=[
                StringFileInfo(
                    [StringTable("040904B0", [StringStruct(k, v) for k, v in strings.items()])]
                ),
                VarFileInfo([VarStruct("Translation", [1033, 1200])]),
            ],
        )

    def program(self) -> tuple[Any, Any]:
        """Analyse the program and describe its executable: ``(Analysis, EXE)`` for the spec.

        Each executable carries its own pure-Python modules; everything else goes in ``lib/``.
        """
        from PyInstaller.building.api import EXE, PYZ
        from PyInstaller.building.build_main import Analysis

        collected = self.dependencies()
        analysis = Analysis(
            [self.entry_script()],
            pathex=[str(self.directory / "src")],
            binaries=collected.binaries,
            datas=collected.datas,
            hiddenimports=collected.hiddenimports,
            hookspath=[],
            hooksconfig={},
            runtime_hooks=[],
            excludes=self.excludes,
            noarchive=False,
        )
        analysis.datas = self.compile_sources(analysis.datas)
        exe = EXE(
            PYZ(analysis.pure),
            analysis.scripts,
            [],
            exclude_binaries=True,
            name=self.script,
            console=self.console,
            icon=str(brand_icon()) if WINDOWS else None,
            version=self.version_info() if WINDOWS else None,
            upx=False,
            # Everything but the executables goes in lib/ (COLLECT follows the EXE).
            contents_directory="lib",
        )
        return analysis, exe


def names(product: Product) -> dict[str, str]:
    """The publisher, install folder and Start Menu folder, which every product shares."""
    settings = build_settings()
    return {
        "PUBLISHER": settings["publisher"],
        "INSTALL_DIR": settings["install-dir"].replace("/", "\\"),
        "START_MENU_DIR": settings["start-menu-dir"].replace("/", "\\"),
    }


class Cli(Product):
    """The command line: ``[project.scripts]`` and ``core-package`` in build.toml."""

    kind = "cli"
    scripts_key = "scripts"
    console = True

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.core_package: str = self.require("core-package")

    def values(self) -> dict[str, str]:
        return {
            "CLI_NAME": self.script,
            "CLI_MODULE": self.module,
            "CLI_PACKAGE": self.package,
            "CORE_PACKAGE": self.core_package,
            "APP_VERSION": self.version,
            "APP_TITLE": self.title,
            **names(self),
        }

    def dependencies(self) -> Collected:
        from PyInstaller.utils.hooks import collect_submodules

        collected = Collected()
        collected.metadata(self.project["name"])
        collected.hiddenimports.extend(collect_submodules(self.core_package))
        collected.hiddenimports.extend(collect_submodules(self.package))
        for package in self.collect:
            collected.package(package)
        return collected


class Ui(Product):
    """The window: ``[project.gui-scripts]``, ``api-package`` and the frontend in build.toml."""

    kind = "ui"
    scripts_key = "gui-scripts"
    console = False
    windows_only = True

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_package: str = self.require("api-package")
        if self.frontend is None:
            raise SystemExit(f"Product {self.name} in build.toml needs frontend.")
        self.dist = self.frontend / self.frontend_dist

    @staticmethod
    def core_package() -> str:
        """The library the window hosts: the command line product says which it is."""
        for product in load_products(all_platforms=True):
            if isinstance(product, Cli):
                return product.core_package
        raise SystemExit("The window needs a product of type cli in installer/build.toml.")

    def values(self) -> dict[str, str]:
        if self.frontend is None:
            raise SystemExit(f"Product {self.name} in build.toml needs frontend.")
        return {
            "UI_DIR": self.frontend.relative_to(ROOT).as_posix(),
            "UI_NAME": self.script,
            "UI_PACKAGE": self.package,
            "API_PACKAGE": self.api_package,
            "UI_VERSION": self.version,
            "UI_TITLE": self.title,
            **names(self),
        }

    def dependencies(self) -> Collected:
        """Windows only.

        Cornea serves the frontend and the API with uvicorn, FastAPI and Starlette, which load
        protocol and middleware modules by name; pywebview reaches WebView2 through pythonnet and
        clr_loader.
        """
        from PyInstaller.utils.hooks import collect_submodules

        if not WINDOWS or importlib.util.find_spec("cornea") is None:
            raise SystemExit(
                "The UI build needs Windows and cornea-shell (uv sync --group installer)."
            )
        if not self.dist.is_dir() or not any(self.dist.iterdir()):
            raise SystemExit(f"Build the frontend first: {self.frontend_build} in {self.frontend}")
        collected = Collected()
        collected.metadata(
            self.project["name"], "cornea-shell", "pywebview", "fastapi", "starlette", "uvicorn",
            "pydantic", "pydantic-settings",
        )  # fmt: skip
        for package in self.collect:
            collected.package(package)
        collected.hiddenimports.extend(collect_submodules(self.core_package()))
        collected.hiddenimports.extend(collect_submodules(self.api_package))
        collected.hiddenimports.extend(collect_submodules(self.package))
        # The window finds the bundle through its package (Static(package=<ui package>, ...)), so it
        # is frozen at the same path under src/.
        src = self.directory / "src"
        collected.datas.append((str(self.dist), self.dist.relative_to(src).as_posix()))
        return collected


PRODUCT_TYPES: dict[str, type[Product]] = {cls.kind: cls for cls in (Cli, Ui)}


def load_products(*, all_platforms: bool = False) -> list[Product]:
    """The ``[[products]]`` of build.toml, in order, without those this OS cannot build."""
    found: list[Product] = []
    for config in build_settings()["products"]:
        kind = config.get("type")
        if kind not in PRODUCT_TYPES:
            raise SystemExit(
                f"Product {config.get('name')} in build.toml has type {kind!r}; "
                f"choose from {', '.join(PRODUCT_TYPES)}."
            )
        cls = PRODUCT_TYPES[kind]
        if cls.windows_only and not (WINDOWS or all_platforms):
            continue
        found.append(cls(config))
    return found


def github_env() -> None:
    """Print the project names and, on GitHub, add them to ``GITHUB_ENV`` for the later steps."""
    values: dict[str, str] = {}
    for product in load_products(all_platforms=True):
        values.update(product.values())
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
            env.write(lines)
    sys.stdout.write(lines)


P = TypeVar("P", bound=Product)


@dataclass(frozen=True)
class Meta:
    """What the installers are built from."""

    products: list[Product]  # the programs this OS builds
    name: str  # file name stem of the setup and zip, and the PyInstaller folder
    version: str  # the setup's own version (installer/build.toml)
    title: str
    publisher: str
    install_dir: str  # folder under Program Files, "/" between parts
    start_menu_dir: str  # folder in the Start Menu, "/" between parts
    licence: Path

    def product(self, kind: type[P]) -> P | None:
        """The first product of that class, if this OS builds one."""
        return next((item for item in self.products if isinstance(item, kind)), None)

    @property
    def cli(self) -> Cli:
        cli = self.product(Cli)
        if cli is None:
            raise SystemExit("installer/build.toml needs a product of type cli.")
        return cli

    @property
    def ui(self) -> Ui | None:  # Windows only
        return self.product(Ui)


def load_meta() -> Meta:
    product = build_settings()
    return Meta(
        products=load_products(),
        name=product["name"],
        version=product["version"],
        title=product["title"],
        publisher=product["publisher"],
        install_dir=product["install-dir"],
        start_menu_dir=product["start-menu-dir"],
        licence=build_file("file", "licence"),
    )


def run(command: list[str], *, env: dict[str, str] | None = None, cwd: Path = ROOT) -> None:
    print("+", " ".join(shlex.quote(part) for part in command), flush=True)
    subprocess.run(command, check=True, cwd=cwd, env=env)


def run_parallel(tasks: list[Callable[[], T]], jobs: int) -> list[T]:
    """Run independent ``tasks`` on up to ``jobs`` threads; results keep the order of ``tasks``.

    The work is in subprocesses (nfpm), so threads are enough. The first failure is raised once
    the others have finished.
    """
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(tasks) or 1))) as pool:
        futures = [pool.submit(task) for task in tasks]
        return [future.result() for future in futures]


def author(meta: Meta) -> dict[str, str]:
    authors = meta.cli.project.get("authors") or [{}]
    return dict(authors[0])


# ---- PyInstaller -------------------------------------------------------------------------------
def freeze(meta: Meta) -> Path:
    """Run PyInstaller on the one spec and return its output folder."""
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(build_file("spec")),
            "--noconfirm",
            "--distpath",
            str(BUILD),
            "--workpath",
            str(WORK / "pyinstaller"),
        ]
    )
    return BUILD / meta.name


# ---- branding: the artwork named under [brand] in installer/build.toml ----------------------
@functools.cache
def build_settings() -> dict[str, Any]:
    """installer/build.toml: the setup's version, names and artwork."""
    return tomllib.loads((INSTALLER / "build.toml").read_text(encoding="utf-8"))


def configured(section: str, key: str) -> Path | None:
    """The file or folder named by ``[<section>] <key>`` (from the repository root), if any."""
    value = build_settings().get(section, {}).get(key)
    if value is None:
        return None
    path = ROOT / value
    if not path.exists():
        raise SystemExit(f"[{section}] {key} in build.toml names {value}, which is missing.")
    return path


def brand(key: str) -> Path | None:
    """A file or folder of artwork named under ``[brand]``, if any."""
    return configured("brand", key)


def build_formats() -> tuple[list[str], list[str]]:
    """The formats of ``[formats]`` in build.toml: the ones this OS builds, and all of them."""
    table: dict[str, list[str]] = build_settings().get("formats", {})
    here = table.get("windows" if WINDOWS else "linux", [])
    return list(here), sorted({name for names in table.values() for name in names})


def build_file(key: str, section: str = "build") -> Path:
    """A required file named under ``[build]`` (``spec``, ``nsi``, ``nfpm``) or another section."""
    path = configured(section, key)
    if path is None:
        raise SystemExit(f"installer/build.toml needs [{section}] {key}.")
    return path


@functools.cache
def brand_icon() -> Path:
    """The icon of the executables, the setup and the uninstaller: ``[brand] icon`` (.ico)."""
    icon = brand("icon")
    if icon is None:
        raise SystemExit("installer/build.toml needs [brand] icon.")
    return icon


def brand_art() -> dict[str, str]:
    """The setup's header and welcome bitmaps, when ``[brand]`` names them (NSIS has defaults)."""
    names = {"HEADER_IMAGE": "header-image", "WELCOME_IMAGE": "welcome-image"}
    return {flag: str(path) for flag, key in names.items() if (path := brand(key)) is not None}


def brand_png_dir() -> Path:
    """The folder with the package icons (app-16.png ... app-256.png): ``[brand] png-dir``."""
    folder = brand("png-dir")
    if folder is None or not sorted(folder.glob("app-*.png")):
        raise SystemExit("installer/build.toml needs [brand] png-dir, a folder with app-*.png.")
    return folder


# ---- Windows: components, NSIS and zip ---------------------------------------------------------
def link_tree(source: Path, target: Path, files: list[Path] | None = None) -> None:
    """Hard-link (or copy) ``files`` of ``source`` (all of them by default) into ``target``."""
    for path in files if files is not None else sorted(source.rglob("*")):
        if path.is_dir():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, destination)
        except OSError:
            shutil.copy2(path, destination)


def split_components(meta: Meta, folder: Path) -> Path:
    """Sort the PyInstaller folder into core/ (shared), cli/ and ui/ under the work folder.

    A program's executable belongs to it; the files of lib/ that only one program needs (the
    spec writes the list) go with it; everything else is shared and is installed once.
    """
    only = json.loads((BUILD / "example-components.json").read_text(encoding="utf-8"))
    exes = {f"{item.script}.exe": item.name for item in meta.products}
    owner = {f"lib/{name}": key for key, names in only.items() for name in names}
    stage = WORK / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    for path in sorted(folder.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(folder).as_posix()
        key = exes.get(relative) or owner.get(relative) or "core"
        link_tree(folder, stage / key, [path])
    for key in ("core", *(item.name for item in meta.products)):
        (stage / key).mkdir(parents=True, exist_ok=True)
    return stage


def nsis_text(value: str) -> str:
    return value.replace("$", "$$").replace('"', '$\\"')


def write_components(meta: Meta, stage: Path) -> Path:
    """The uninstall macros of the setup: what each program installed, to remove it alone."""
    lines = ["; Written by build.py: what each program put in the install folder."]
    for item in meta.products:
        macro = f"Remove_{item.name}"
        base = stage / item.name
        found = sorted(base.rglob("*"))
        lines.append(f"!macro {macro}")
        for path in found:
            if path.is_file():
                lines.append(f'  Delete "$INSTDIR\\{nsis_text(str(path.relative_to(base)))}"')
        folders = sorted((p for p in found if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
        for path in folders:
            lines.append(f'  RMDir "$INSTDIR\\{nsis_text(str(path.relative_to(base)))}"')
        lines.append("!macroend")
    target = WORK / "components.nsh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def sign(files: list[Path]) -> None:
    """Sign ``files`` with SIGN_COMMAND, if it is set; otherwise do nothing."""
    template = os.environ.get("SIGN_COMMAND", "").strip()
    if not template:
        return
    if "{file}" not in template:
        raise SystemExit("SIGN_COMMAND must contain {file}, where the file to sign goes.")
    for file in files:
        command = template.replace("{file}", f'"{file}"')
        print("+", command, flush=True)
        # Windows takes the command line as written; elsewhere it is split like a shell would.
        # SIGN_COMMAND is set by whoever runs the build (a CI variable), so it is trusted input.
        subprocess.run(command if WINDOWS else shlex.split(command), check=True, cwd=ROOT)


def find_makensis() -> str:
    found = shutil.which("makensis")
    if found:
        return found
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        candidate = Path(os.environ.get(variable, "")) / "NSIS" / "makensis.exe"
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("makensis not found. Install NSIS (version in installer/tools.toml).")


def numeric_version(version: str) -> str:
    numbers = re.findall(r"\d+", version)[:4]
    return ".".join(numbers + ["0"] * (4 - len(numbers)))


def package_exe(meta: Meta, folder: Path) -> Path:
    """Build the one NSIS setup with both programs."""
    if meta.ui is None:
        raise SystemExit("The setup needs the UI product in build.toml.")
    OUT.mkdir(parents=True, exist_ok=True)
    sign(sorted(folder.glob("*.exe")))
    stage = split_components(meta, folder)
    setup = OUT / f"{meta.name}-{meta.version}-full-setup.exe"
    links = build_settings().get("links", {})
    flags = {
        "GUID": build_settings()["guid"],
        "APP_NAME": meta.title,
        "APP_VERSION": meta.version,
        "APP_VERSION_NUMERIC": numeric_version(meta.version),
        "STAGE_DIR": str(stage),
        "COMPONENTS_FILE": str(write_components(meta, stage)),
        "CLI_EXE": f"{meta.cli.script}.exe",
        "CLI_VERSION": meta.cli.version,
        "UI_EXE": f"{meta.ui.script}.exe",
        "UI_VERSION": meta.ui.version,
        "OUT_FILE": str(setup),
        "ICON_FILE": str(brand_icon()),
        **brand_art(),
        "LICENSE_FILE": str(meta.licence),
        "PUBLISHER": meta.publisher,
        "INSTALL_DIR": meta.install_dir.replace("/", "\\"),
        "INSTALL_DIR_DEPTH": len(meta.install_dir.split("/")),
        "START_MENU_DIR": meta.start_menu_dir.replace("/", "\\"),
        "START_MENU_DIR_DEPTH": len(meta.start_menu_dir.split("/")),
        "SUPPORT_URL": str(links.get("issues", "")),
        "UPDATE_URL": str(links.get("changelog", "")),
        "URL": str(links.get("homepage", "")),
    }
    command = [find_makensis(), "/V2"]
    command += [f"/D{key}={value}" for key, value in flags.items() if value]
    run([*command, str(build_file("nsi"))])
    sign([setup])
    return setup


def write_manifest(meta: Meta) -> Path:
    """What the setup contains, beside it: the setup's version and each program's."""
    if meta.ui is None:
        raise SystemExit("The setup needs the UI product in build.toml.")
    manifest = OUT / f"{meta.name}-{meta.version}-components.json"
    contents = {
        "setup": meta.version,
        "components": {item.script: item.version for item in meta.products},
    }
    manifest.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    return manifest


def package_zip(meta: Meta) -> Path:
    """The command line alone as a portable zip (what the Scoop manifest installs)."""
    OUT.mkdir(parents=True, exist_ok=True)
    stage = WORK / "stage"
    merged = WORK / "zip"
    shutil.rmtree(merged, ignore_errors=True)
    for key in ("core", meta.cli.name):
        link_tree(stage / key, merged)
    target = OUT / f"{meta.name}-{meta.cli.version}-windows-x64"
    return Path(shutil.make_archive(str(target), "zip", root_dir=merged))


# ---- Linux -------------------------------------------------------------------------------------
def normalise_modes(folder: Path) -> None:
    """Folders 755, files 644, and 755 for anything executable, whatever the build umask was."""
    for path in [folder, *folder.rglob("*")]:
        if path.is_symlink():
            continue
        if path.is_dir() or path.stat().st_mode & stat.S_IXUSR or ".so" in path.name:
            path.chmod(0o755)
        else:
            path.chmod(0o644)


def package_linux(meta: Meta, folder: Path, formats: list[str], jobs: int) -> list[Path]:
    """Build the deb and rpm packages of the command line."""
    normalise_modes(folder)
    OUT.mkdir(parents=True, exist_ok=True)
    machine = platform.machine().lower()
    who = author(meta)
    maintainer = who.get("name", "")
    if who.get("email"):
        maintainer = f"{maintainer} <{who['email']}>"
    links = build_settings().get("links", {})
    env = {
        **os.environ,
        "PKG_NAME": meta.cli.script,
        "PKG_VERSION": str(meta.cli.version),
        "PKG_ARCH": {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64"}.get(machine, machine),
        "PKG_DESCRIPTION": str(meta.cli.project.get("description", meta.name)),
        "PKG_MAINTAINER": maintainer,
        "PKG_HOMEPAGE": str(links.get("homepage", "")),
        "PKG_LICENSE": str(meta.cli.project.get("license", "")),
        "PKG_SOURCE_DIR": str(folder),
        "PKG_LICENSE_FILE": str(meta.licence),
        "PKG_ICON_DIR": str(brand_png_dir()),
    }
    nfpm = shlex.split(os.environ.get("NFPM", "nfpm"))
    if shutil.which(nfpm[0]) is None:
        raise SystemExit(
            "nfpm not found. Install it (version in installer/tools.toml) or set NFPM."
        )
    before = set(OUT.iterdir())

    def package(packager: str) -> None:
        run(
            [*nfpm, "package", "--config", str(build_file("nfpm")),
             "--packager", packager, "--target", str(OUT)],
            env=env,
        )  # fmt: skip

    run_parallel([functools.partial(package, packager) for packager in formats], jobs)
    return sorted(set(OUT.iterdir()) - before)


# ---- driver ------------------------------------------------------------------------------------
def sync() -> None:
    """Install the products and the installer dependency group, and nothing else."""
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("--sync needs uv on PATH.")
    scope = ["--all-packages"] if WINDOWS else ["--package", "example-cli"]
    run([uv, "sync", *scope, "--group", "installer", "--no-dev"])


def build_frontend(meta: Meta) -> None:
    """Build the frontend of each product that has one: it is frozen into the build."""
    for item in meta.products:
        item.build_frontend()


def smoke(meta: Meta) -> None:
    """Start each built program and check it answers: the ``smoke`` test of each product."""
    for item in meta.products:
        if item.smoke:
            run(
                [sys.executable, "-m", "pytest", *build_settings()["build"]["smoke-args"],
                 item.smoke],
                cwd=item.directory,
            )  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Example App installers.")
    parser.add_argument("--sync", action="store_true", help="uv sync the installer group first")
    parser.add_argument("--smoke", action="store_true", help="run the smoke tests on the build")
    parser.add_argument("--github-env", action="store_true",
                        help="add the project names to GITHUB_ENV, print them, stop")  # fmt: skip
    parser.add_argument("--build-frontend", action="store_true",
                        help="run npm ci && npm run build first (Windows)")  # fmt: skip
    allowed, known = build_formats()
    parser.add_argument(
        "--format",
        metavar="exe,deb,rpm",
        help=f"comma-separated formats, here: {', '.join(allowed)} (default: all)",
    )
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                        help="builds to run at once (1 = one after the other)")  # fmt: skip
    args = parser.parse_args()

    if args.github_env:
        github_env()
        return
    if not (WINDOWS or LINUX):
        raise SystemExit("Installers are built on Windows (setup.exe) and Linux (deb, rpm) only.")
    formats = [f.strip() for f in args.format.split(",") if f.strip()] if args.format else []
    unknown = sorted(set(formats) - set(known))
    if unknown:
        parser.error(f"unknown format: {', '.join(unknown)} (choose from {', '.join(known)})")
    wrong = [f for f in formats if f not in allowed]
    if wrong:
        raise SystemExit(
            f"--format {','.join(wrong)} cannot be built on this OS (here: {', '.join(allowed)})."
        )
    formats = formats or allowed

    if args.sync:
        sync()
    meta = load_meta()
    if args.build_frontend:
        build_frontend(meta)
    folder = freeze(meta)
    if WINDOWS:
        brand_icon()  # fail early, before the setup is built
        # The zip reads the folders the setup is staged into, so the setup goes first.
        built = [package_exe(meta, folder), write_manifest(meta), package_zip(meta)]
    else:
        built = package_linux(meta, folder, formats, args.jobs)
    if args.smoke:
        smoke(meta)
    print("\nBuilt:")
    for path in built:
        print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
