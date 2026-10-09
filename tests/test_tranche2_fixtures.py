from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures" / "tranche2"
EXPECTED = [*(f"R{i:02d}" for i in range(1, 18)), *(f"C{i:02d}-v{v}" for i in range(1, 9) for v in range(1, 4)), *(f"S{i:02d}" for i in range(1, 6))]


def test_tranche2_fixture_inventory_and_contract() -> None:
    assert sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()) == sorted(EXPECTED)
    for fixture_id in EXPECTED:
        root = FIXTURES / fixture_id
        assert (root / "prompt.md").is_file()
        assert (root / "public").is_dir()
        assert (root / "manifest.json").is_file()
        assert (root / "verifier" / "verify.py").is_file()
        assert (root / "known_good" / "solve.py").is_file()
        assert (root / "mutants").is_dir()
        manifest = json.loads((root / "manifest.json").read_text())
        assert manifest["fixture_id"] == fixture_id
        assert manifest["expected_checks"] > 0
        assert manifest["allowed_mutation_paths"] == ["work/**"]
        assert manifest["immutable_hashes"]


def test_reasoning_envelopes_are_strict_and_admitted() -> None:
    for fixture_id in (f"R{i:02d}" for i in range(1, 18)):
        manifest = json.loads((FIXTURES / fixture_id / "manifest.json").read_text())
        assert manifest["answer_schema"] == {
            "type": "object",
            "required": ["answer", "evidence_ids"],
            "additionalProperties": False,
        }
        receipt = json.loads((FIXTURES / fixture_id / "admission.json").read_text())
        assert receipt["status"] == "admitted"
        assert receipt["reference_runs"] == 2
        assert receipt["deterministic"] is True
        assert receipt["negative_controls_passed"] is True


def test_every_fixture_readmits_from_fresh_copies() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/admit_tranche2.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["admitted"] == len(EXPECTED)
    assert report["failed"] == 0


def test_cross_cutting_artifacts_are_real() -> None:
    corpus = FIXTURES / "S03" / "public" / "corpus.txt"
    assert corpus.stat().st_size > 200_000
    scene = json.loads((FIXTURES / "S04" / "public" / "scene_graph.json").read_text())
    assert scene["elements"] and (FIXTURES / "S04" / "public" / "dashboard.svg").is_file()
    trace = json.loads((FIXTURES / "S05" / "public" / "trace.json").read_text())
    assert trace["calls"] and len(trace["harnesses"]) >= 2


def test_coding_variants_contain_source_without_public_oracles() -> None:
    for fixture_id in (f"C{i:02d}-v{v}" for i in range(1, 9) for v in range(1, 4)):
        root = FIXTURES / fixture_id
        assert list((root / "public" / "src").glob("*.py"))
        assert not (root / "public" / "tests").exists()
        assert "public/tests" not in (root / "prompt.md").read_text()
        assert list((root / "mutants").glob("*.py"))


def test_coding_hidden_contracts_execute_candidates_and_variants_are_substantive() -> None:
    for family in range(1, 9):
        variant_hashes = {"hidden": set(), "mutant": set()}
        for variant in range(1, 4):
            root = FIXTURES / f"C{family:02d}-v{variant}"
            contract = root / "verifier" / "contract.py"
            cases = root / "verifier" / "cases.json"
            good = subprocess.run(
                [sys.executable, str(contract), str(root / "known_good" / "solution.py"), str(cases)],
                text=True, capture_output=True, timeout=10,
            )
            bad = subprocess.run(
                [sys.executable, str(contract), str(next((root / "mutants").glob("*.py"))), str(cases)],
                text=True, capture_output=True, timeout=10,
            )
            assert good.returncode == 0, good.stdout + good.stderr
            assert bad.returncode != 0, "hidden contract must exercise and reject the variant mutant"
            paths = {
                "hidden": cases,
                "mutant": next((root / "mutants").glob("*.py")),
            }
            for kind, path in paths.items():
                variant_hashes[kind].add(hashlib.sha256(path.read_bytes()).hexdigest())
        assert all(len(hashes) == 3 for hashes in variant_hashes.values())
