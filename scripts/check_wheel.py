"""Check the built wheel against the source assets; never contact public providers."""

import hashlib
import json
import zipfile
from pathlib import Path

REQUIRED = (
    "uk_data_mcp/server.py", "uk_data_mcp/deskstudy.py", "uk_data_mcp/reporting.py",
    "uk_data_mcp/report_contract.py", "uk_data_mcp/json_safety.py", "uk_data_mcp/coverage.py",
    "uk_data_mcp/groundwater.py", "uk_data_mcp/sources.json", "uk_data_mcp/demo_desk_study.json",
    "uk_data_mcp/web/index.html", "uk_data_mcp/web/app.js", "uk_data_mcp/web/styles.css",
)


def main():
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel from a clean build.")
    checks = {}
    with zipfile.ZipFile(wheels[0]) as archive:
        for name in REQUIRED:
            packaged = archive.read(name)
            expected = (Path("src") / name).read_bytes()
            if packaged != expected:
                raise SystemExit(f"Packaged file does not match source: {name}")
            checks[name] = hashlib.sha256(packaged).hexdigest()
    output = Path("ci-results")
    output.mkdir(exist_ok=True)
    (output / "wheel.json").write_text(
        json.dumps({"wheel": wheels[0].name, "files_sha256": checks}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Verified {len(checks)} required wheel files against source.")


if __name__ == "__main__":
    main()
