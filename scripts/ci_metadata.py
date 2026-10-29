"""Record only non-secret reproducibility metadata for this CI run."""

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path


def main():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    versions = {}
    for name in ("uk-data-mcp-servers", "mcp", "httpx", "starlette", "uvicorn", "pytest", "ruff"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    output = Path("ci-results")
    output.mkdir(exist_ok=True)
    (output / "environment.json").write_text(
        json.dumps({"commit": revision, "python": sys.version, "platform": platform.platform(),
                    "packages": versions}, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
