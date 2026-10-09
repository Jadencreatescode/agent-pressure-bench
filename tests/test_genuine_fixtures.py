from __future__ import annotations

import json
from pathlib import Path

from agent_pressure_bench.adapters import FixtureAdapter
from agent_pressure_bench.fixtures import discover_fixtures, verify_fixture
from agent_pressure_bench.runner import BenchmarkRunner, RunConfig, digest_json
from agent_pressure_bench.verification import verify_run

ROOT = Path(__file__).parents[1]


def test_tranche_one_has_60_admitted_real_fixture_directories() -> None:
    fixtures = [p for name in ("bounded", "long-horizon", "heldout", "failure-edge")
                for p in discover_fixtures(ROOT / "fixtures" / name)]
    assert len(fixtures) == 60
    assert {p.name.split("-")[0] for p in fixtures} == {
        *(f"B{i:02d}" for i in range(1, 9)),
        *(f"L{i:02d}" for i in range(1, 4)),
        *(f"H{i:02d}" for i in range(1, 4)),
        *(f"F{i:02d}" for i in range(1, 7)),
    }
    for fixture in fixtures:
        manifest = json.loads((fixture / "manifest.json").read_text())
        receipt = json.loads((fixture / "admission.json").read_text())
        assert (fixture / "prompt.md").is_file()
        assert (fixture / "public").is_dir()
        assert (fixture / "verifier" / "verify.py").is_file()
        assert (fixture / "reference" / "solve.py").is_file()
        assert (fixture / "mutants" / "targeted.py").is_file()
        assert manifest["expected_checks"] > 0
        assert manifest["allowed_paths"] == ["work/answer.json"]
        assert receipt["admitted"] is True
        assert receipt["reference_runs"][0]["semantic_hash"] == receipt["reference_runs"][1]["semantic_hash"]
        assert receipt["mutant_run"]["passed"] is False
        assert receipt["expected_checks"] == receipt["enumerated_checks"] == receipt["reported_checks"]
        assert verify_fixture(fixture, fixture / "reference_snapshot")["passed"] is True


def test_runner_materializes_public_inputs_and_external_verifier_from_snapshot(tmp_path: Path) -> None:
    suite = json.loads((ROOT / "suites" / "bounded.json").read_text())
    run = BenchmarkRunner(FixtureAdapter(), RunConfig(tmp_path / "runs")).run_suite(
        suite, admission_digest=digest_json(suite)
    )
    result = json.loads((run / "result.json").read_text())
    assert result["summary"] == {"total": 24, "passed": 24, "failed": 0, "executed_tool_calls": 24}
    for task in suite["tasks"]:
        snap = run / "workspace" / task["id"]
        assert (snap / "public").is_dir()
        assert (snap / "work" / "answer.json").is_file()
        assert not (snap / "reference").exists()
        assert not (snap / "verifier").exists()
        assert "expected" not in (snap / "prompt.md").read_text().lower()
    assert verify_run(run, trusted_suite_digest=digest_json(suite))["valid"] is True


def test_heldout_generator_has_runnable_track_and_sealed_samples() -> None:
    generator = json.loads((ROOT / "suites" / "heldout-generator.json").read_text())
    assert generator["track"] == "heldout_generator"
    assert generator["sample_count"] == 9
    for fixture in discover_fixtures(ROOT / "fixtures" / "heldout"):
        manifest = json.loads((fixture / "manifest.json").read_text())
        assert manifest["sealed"] is True
        assert manifest["sealed_before_candidate"] is True
        assert manifest["generator_seed_hash"]
