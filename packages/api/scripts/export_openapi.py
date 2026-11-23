#!/usr/bin/env python3
"""Write the OpenAPI document to packages/api/docs/openapi.json.

CI regenerates it and fails if it differs, so the committed contract always matches the code.
Usage: uv run python packages/api/scripts/export_openapi.py
"""

import json
import os
from pathlib import Path

from example_api.config import Settings

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"

# The contract does not depend on settings; avoid needing an API key to build the app.
_prefix = Settings.model_config["env_prefix"]
os.environ.setdefault(f"{_prefix}AUTH_MODE", "none")
os.environ[f"{_prefix}DOCS_ENABLED"] = "true"


def main() -> None:
    from example_api.main import create_app

    spec = create_app().openapi()
    OUTPUT.write_text(
        json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
