#!/usr/bin/env python3
"""Generate a deterministic CycloneDX JSON SBOM from uv.lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/sbom.cdx.json"))
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    metadata = project["project"]
    components = []
    for package in sorted(lock.get("package", []), key=lambda p: (p["name"], p["version"])):
        if package["name"] == metadata["name"]:
            continue
        component = {
            "type": "library",
            "name": package["name"],
            "version": package["version"],
            "bom-ref": f"pkg:pypi/{package['name']}@{package['version']}",
            "purl": f"pkg:pypi/{package['name']}@{package['version']}",
        }
        components.append(component)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-4000-8000-000000000000",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": metadata["name"],
                "version": metadata["version"],
                "bom-ref": f"pkg:pypi/{metadata['name']}@{metadata['version']}",
                "purl": f"pkg:pypi/{metadata['name']}@{metadata['version']}",
            },
            "properties": [
                {"name": "apb:source-lockfile", "value": "uv.lock"},
                {"name": "apb:source-lockfile-sha256", "value": sha256(ROOT / "uv.lock")},
                {"name": "apb:scope", "value": "locked development and build environment"},
            ],
        },
        "components": components,
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {output} with {len(components)} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
