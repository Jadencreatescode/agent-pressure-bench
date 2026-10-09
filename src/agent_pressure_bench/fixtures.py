from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import atexit
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any


_RESOURCE_CONTEXTS = ExitStack()
atexit.register(_RESOURCE_CONTEXTS.close)


def fixture_root() -> Path:
    configured = os.environ.get("APB_FIXTURE_ROOT")
    if configured:
        return Path(configured)
    root = _RESOURCE_CONTEXTS.enter_context(
        as_file(files("agent_pressure_bench").joinpath("fixtures"))
    )
    if not root.is_dir():
        raise FileNotFoundError("packaged fixture resources are unavailable")
    return root


def discover_fixtures(root: Path | None = None) -> list[Path]:
    base = root or fixture_root()
    if not base.exists():
        return []
    return sorted(p.parent for p in base.rglob("manifest.json"))


def find_fixture(fixture_id: str, root: Path | None = None) -> Path:
    matches = [p for p in discover_fixtures(root) if p.name == fixture_id]
    if len(matches) != 1:
        raise ValueError(f"fixture id must resolve exactly once: {fixture_id}")
    return matches[0]


def file_hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()}


def materialize_fixture(fixture: Path, snapshot: Path) -> None:
    snapshot.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture / "prompt.md", snapshot / "prompt.md")
    shutil.copytree(fixture / "public", snapshot / "public", dirs_exist_ok=True)
    (snapshot / "work").mkdir(exist_ok=True)


def verify_fixture(fixture: Path, snapshot: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(fixture / "verifier" / "verify.py"), str(snapshot)],
        text=True, capture_output=True, env={**os.environ, "TZ": "UTC", "LC_ALL": "C"}, timeout=30,
    )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"fixture verifier emitted invalid JSON: {proc.stderr}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("fixture verifier result must be an object")
    result["process_returncode"] = proc.returncode
    return result
