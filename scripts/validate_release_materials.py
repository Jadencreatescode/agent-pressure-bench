#!/usr/bin/env python3
"""Validate public release metadata without network access."""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent_pressure_bench.validation import validate_provenance

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "CITATION.cff", "PROVENANCE.json", "RELEASE_CHECKLIST.md", "LICENSE",
    "NOTICE", "SECURITY.md", "REPORTING_POLICY.md", "HIDDEN_SUITE_ARCHITECTURE.md",
    "docs/index.html", ".env.example", ".gitignore",
]


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail("missing release files: " + ", ".join(missing))
    provenance = json.loads((ROOT / "PROVENANCE.json").read_text())
    try:
        validate_provenance(ROOT)
    except ValueError as exc:
        fail(str(exc))
    declared = {item["path"] for item in provenance["materials"]}
    suite_paths = {p.relative_to(ROOT).as_posix() for p in (ROOT / "suites").glob("*.json")}
    result_paths = {p.relative_to(ROOT).as_posix() for p in (ROOT / "results").glob("*.json")}
    absent = sorted((suite_paths | result_paths) - declared)
    if absent:
        fail("provenance omissions: " + ", ".join(absent))
    for item in provenance["materials"]:
        path = ROOT / item["path"]
        if not path.is_file():
            fail(f"provenance path does not exist: {item['path']}")
    readme = (ROOT / "README.md").read_text()
    for target in re.findall(r"\[[^]]+\]\(([^)#]+)", readme):
        if "://" not in target and not (ROOT / target).exists():
            fail(f"README link target missing: {target}")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text()
        if "pull_request_target:" in text:
            fail(f"unsafe pull_request_target trigger: {workflow.name}")
        for action in re.findall(r"uses:\s*([^\s#]+)", text):
            ref = action.rsplit("@", 1)[-1]
            if workflow.name == "ci.yml" and not re.fullmatch(r"[0-9a-f]{40}", ref):
                fail(f"CI action is not SHA-pinned: {action}")
    excluded_roots = {".git", ".venv", "venv", "artifacts", "build", "dist"}
    cache_dirs = [
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("__pycache__")
        if not excluded_roots.intersection(p.relative_to(ROOT).parts)
    ]
    if cache_dirs:
        fail("generated caches present: " + ", ".join(cache_dirs))
    print(f"release metadata valid: {len(declared)} provenance records, {len(REQUIRED)} required files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
