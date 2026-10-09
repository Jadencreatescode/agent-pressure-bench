from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_pressure_bench.adapters import FixtureAdapter, ScriptedAdapter
from agent_pressure_bench.fixtures import find_fixture, materialize_fixture, verify_fixture
from agent_pressure_bench.runner import BenchmarkRunner, RunConfig, digest_json

ROOT = Path(__file__).parents[1]
SUITES = (
    "progressive-reasoning", "executable-coding", "structured-output", "safety",
    "long-context", "vision-format", "harness-contract",
)


def _suite(name: str) -> dict:
    return json.loads((ROOT / "suites" / f"{name}.json").read_text())


def test_tranche2_manifests_contain_no_answer_oracle_or_fixture_shortcut() -> None:
    forbidden = {"value", "expected", "oracle", "final", "fixture_response"}
    total = 0
    for name in SUITES:
        suite = _suite(name)
        total += len(suite["tasks"])
        for task in suite["tasks"]:
            assert task["verifier"]["type"] == "fixture"
            assert not forbidden.intersection(task)
            assert not forbidden.intersection(task["verifier"])
            serialized = json.dumps(task, sort_keys=True).lower()
            assert '"expected"' not in serialized
            assert '"oracle"' not in serialized
    assert total == 48


def test_materialized_tranche2_workspace_exposes_only_candidate_inputs(tmp_path: Path) -> None:
    for fixture_id in ("R01", "C01-v1", "S01", "S02", "S03", "S04", "S05"):
        snapshot = tmp_path / fixture_id
        materialize_fixture(find_fixture(fixture_id), snapshot)
        paths = {str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()}
        assert "prompt.md" in paths
        assert not any("oracle" in p or p.startswith("verifier/") or p.startswith("known_good/") for p in paths)
        assert not any(p.endswith("cases.json") or p.startswith("public/tests/") for p in paths)


def test_fixture_adapter_executes_all_tranche2_tracks(tmp_path: Path) -> None:
    for name in SUITES:
        suite = _suite(name)
        run = BenchmarkRunner(FixtureAdapter(), RunConfig(tmp_path / name)).run_suite(
            suite, admission_digest=digest_json(suite)
        )
        result = json.loads((run / "result.json").read_text())
        assert result["summary"]["passed"] == result["summary"]["total"]
        assert result["summary"]["executed_tool_calls"] >= result["summary"]["total"]
        for task in result["tasks"]:
            assert task["verification"] == "external fixture verifier"
            assert task["external_checks"] > 0


def test_reasoning_rejects_bad_envelopes_and_wrong_evidence(tmp_path: Path) -> None:
    fixture = find_fixture("R01")
    for index, payload in enumerate((
        {"answer": 31},
        {"answer": 31, "evidence_ids": ["F2"]},
        {"answer": 31, "evidence_ids": ["F3"], "extra": True},
    )):
        snapshot = tmp_path / str(index)
        materialize_fixture(fixture, snapshot)
        (snapshot / "work" / "answer.json").write_text(json.dumps(payload))
        assert verify_fixture(fixture, snapshot)["passed"] is False


def test_coding_verifier_runs_contract_in_child_process_and_requires_mutation(tmp_path: Path) -> None:
    fixture = find_fixture("C01-v1")
    reference = tmp_path / "reference"
    materialize_fixture(fixture, reference)
    shutil.copy2(fixture / "known_good" / "solution.py", reference / "work" / "solution.py")
    good = verify_fixture(fixture, reference)
    assert good["passed"] is True
    assert good["subprocess_checks"] > 0

    mutant = tmp_path / "mutant"
    materialize_fixture(fixture, mutant)
    manifest = json.loads((fixture / "manifest.json").read_text())
    mutant_paths = sorted(path for path in manifest["immutable_hashes"] if path.startswith("mutants/"))
    assert len(mutant_paths) == 1
    shutil.copy2(fixture / mutant_paths[0], mutant / "work" / "solution.py")
    assert verify_fixture(fixture, mutant)["passed"] is False

    missing = tmp_path / "missing"
    materialize_fixture(fixture, missing)
    assert verify_fixture(fixture, missing)["passed"] is False


def test_cross_cutting_mutants_fail_and_references_pass(tmp_path: Path) -> None:
    mutant_names = {
        "S01": "extra_field.py", "S02": "follows_injection.py", "S03": "includes_distractor.py",
        "S04": "reads_occluded.py", "S05": "drops_call.py",
    }
    for fixture_id, mutant_name in mutant_names.items():
        fixture = find_fixture(fixture_id)
        reference = tmp_path / fixture_id / "reference"
        materialize_fixture(fixture, reference)
        shutil.copy2(fixture / "reference_snapshot" / "work" / "answer.json", reference / "work" / "answer.json")
        assert verify_fixture(fixture, reference)["passed"] is True

        mutant = tmp_path / fixture_id / "mutant"
        materialize_fixture(fixture, mutant)
        # Mutant programs create the bad persisted candidate artifact.
        import subprocess, sys
        subprocess.run([sys.executable, str(fixture / "mutants" / mutant_name), str(mutant)], check=True)
        assert verify_fixture(fixture, mutant)["passed"] is False
