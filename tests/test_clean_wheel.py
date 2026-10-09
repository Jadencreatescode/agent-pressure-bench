from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=180)


def test_clean_wheel_runs_every_public_suite_without_fixture_override(tmp_path: Path) -> None:
    # A release build must never consume stale setuptools output.
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    dist = tmp_path / "dist"
    build = run(["uv", "build", "--wheel", "--out-dir", str(dist)], cwd=ROOT, env=dict(os.environ))
    assert build.returncode == 0, build.stderr
    wheel = next(dist.glob("*.whl"))
    assert wheel.stat().st_size < 5 * 1024 * 1024
    with zipfile.ZipFile(wheel) as archive:
        fixture_prefix = "agent_pressure_bench/fixtures/"
        packaged = {name.removeprefix(fixture_prefix) for name in archive.namelist() if name.startswith(fixture_prefix)}
        expected = {
            path.relative_to(ROOT / "src" / "agent_pressure_bench" / "fixtures").as_posix()
            for path in (ROOT / "src" / "agent_pressure_bench" / "fixtures").rglob("*")
            if path.is_file()
        }
        assert packaged == expected
        assert not any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in archive.namelist())
        assert any(name.endswith("/prompt.md") for name in packaged)
        assert any("/public/" in name for name in packaged)
        assert any("/verifier/verify.py" in name for name in packaged)
        assert any("/reference/solve.py" in name for name in packaged)
        assert any("/mutants/targeted.py" in name for name in packaged)
        assert any(name.endswith("/admission.json") for name in packaged)
        assert b"/Users/thebridge" not in b"".join(archive.read(name) for name in archive.namelist())

    venv = tmp_path / "venv"
    created = run(["uv", "venv", "--python", sys.executable, str(venv)], cwd=tmp_path, env=dict(os.environ))
    assert created.returncode == 0, created.stderr
    installed = run(["uv", "pip", "install", "--python", str(venv / "bin" / "python"), str(wheel)], cwd=tmp_path, env=dict(os.environ))
    assert installed.returncode == 0, installed.stderr

    env = {key: value for key, value in os.environ.items() if key not in {"APB_FIXTURE_ROOT", "PYTHONPATH"}}
    python = str(venv / "bin" / "python")
    listed = run([python, "-m", "agent_pressure_bench", "list"], cwd=tmp_path, env=env)
    assert listed.returncode == 0, listed.stderr
    suites = [line.split("\t", 1)[0] for line in listed.stdout.splitlines() if line]
    assert len(suites) == 11

    reports: dict[str, dict[str, object]] = {}
    for suite in suites:
        result = run(
            [python, "-m", "agent_pressure_bench", "run", suite, "--adapter", "fixture", "--output", str(tmp_path / "runs")],
            cwd=tmp_path,
            env=env,
        )
        assert result.returncode == 0, f"{suite}: {result.stderr}\n{result.stdout}"
        reports[suite] = json.loads(result.stdout)
    assert all(report["verified"] is True and report["failed"] == 0 for report in reports.values())
