# PyInstaller spec for the command line and, on Windows, the desktop window, in one folder.
#
#   example(.exe)    the command line (console)
#   example-ui.exe     the window (no console), Windows only
#   lib/            the Python runtime and the dependencies of both
#
# One-folder build on purpose (no one-file build). Names, version, icon and dependencies: see
# the Product classes in installer/scripts/build.py, one per [[products]] entry of
# installer/build.toml. example-components.json lists
# the files of lib/ that only one program needs, so the setup can install and remove them with
# that program and keep the rest while either stays. The *.dist-info folders are left out;
# their licence texts are gathered in lib/THIRD_PARTY_LICENSES.txt.
# Build the frontend first (npm ci && npm run build in packages/ui/src/example_ui/ui):
#   uv sync --group installer
#   uv run python installer/scripts/build.py

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH).parent / "scripts"))
import build  # noqa: E402
from PyInstaller.config import CONF  # noqa: E402

analyses = {}
programs = []
for product in build.load_products():
    analysis, exe = product.program()
    analyses[product.name] = analysis
    programs.append(exe)


def files(toc):
    """The entries by destination, without the *.dist-info folders (not read at run time)."""
    entries = {entry[0].replace("\\", "/"): entry for entry in toc}
    return {dest: entry for dest, entry in entries.items() if ".dist-info/" not in dest}


def licences():
    """One file with the licence texts of the *.dist-info folders left out, to ship in lib/."""
    found = {}
    for analysis in analyses.values():
        for entry in analysis.datas:
            dest = entry[0].replace("\\", "/")
            folder, _, name = dest.partition(".dist-info/")
            if not name or not folder or "/" in folder:
                continue
            found.setdefault(folder, {})[dest] = Path(entry[1])
    rule = "=" * 78
    parts = ["Third-party software in this folder, with its licences.\n"]
    for folder, items in sorted(found.items()):
        parts.append(f"\n{rule}\n{folder}\n{rule}\n")
        wanted = [
            path for dest, path in sorted(items.items())
            if path.name.upper().startswith(("LICEN", "COPYING", "NOTICE", "AUTHORS"))
        ]  # fmt: skip
        for path in wanted or [path for path in items.values() if path.name == "METADATA"]:
            text = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"\n--- {path.name} ---\n{text}")
    target = Path(CONF["workpath"]) / "THIRD_PARTY_LICENSES.txt"
    target.write_text("".join(parts), encoding="utf-8")
    return (target.name, str(target), "DATA")


def merge(kind):
    """One entry per destination; two programs may not put different files in the same place."""
    merged = {}
    for key, analysis in analyses.items():
        for dest, entry in files(getattr(analysis, kind)).items():
            if dest in merged and merged[dest][1] != entry[1]:
                raise SystemExit(f"{dest} is a different file in the command line and the window.")
            merged.setdefault(dest, entry)
    return list(merged.values())


used = {key: set(files(a.binaries)) | set(files(a.datas)) for key, a in analyses.items()}
only = {key: sorted(names - set().union(*(v for k, v in used.items() if k != key)))
        for key, names in used.items()}  # fmt: skip
Path(DISTPATH, "example-components.json").write_text(json.dumps(only, indent=1), encoding="utf-8")

coll = COLLECT(
    *programs,
    merge("binaries"),
    [*merge("datas"), licences()],
    name=build.build_settings()["name"],
    upx=False,
)
