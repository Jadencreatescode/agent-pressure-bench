from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from agent_pressure_bench.adapters import ScriptedAdapter
from agent_pressure_bench.runner import BenchmarkRunner, RunConfig, canonical
from agent_pressure_bench.tools import TOOL_SCHEMAS, ToolError, ToolExecutor
from agent_pressure_bench.verification import verify_run
from agent_pressure_bench.validation import validate_provenance, validate_suite, validate_suite_metadata


def suite() -> dict:
    return {"schema_version": "1.0", "id": "integrity", "track": "bounded", "tasks": [{
        "id": "one", "family": "x", "difficulty": 1, "prompt": "write", "budget": 1,
        "verifier": {"type": "file_equals", "path": "answer.txt", "value": "42"},
    }]}


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def make_run(tmp_path: Path) -> tuple[Path, str]:
    admitted = suite()
    adapter = ScriptedAdapter([[{"tool_calls": [{"id": "1", "name": "write_file", "arguments": {
        "path": "answer.txt", "content": "42"}}]}, {"content": "sensitive model response"}]])
    run = BenchmarkRunner(adapter, RunConfig(tmp_path / "runs", requested_route="test", effective_route="scripted",
                                             seed=7)).run_suite(admitted, admission_digest=digest(admitted))
    return run, digest(admitted)


def test_core_has_no_process_tool_and_rejects_all_process_escape_shapes(tmp_path: Path) -> None:
    root = tmp_path / "workspace"; root.mkdir()
    outside = tmp_path / "canary"; outside.write_text("unchanged")
    before = hashlib.sha256(outside.read_bytes()).hexdigest()
    tools = ToolExecutor(root)
    assert "process" not in {s["function"]["name"] for s in TOOL_SCHEMAS}
    attacks = [
        {"argv": [sys.executable, "-c", "print(1)"]},
        {"argv": ["/bin/sh", "-c", "echo pwned"]},
        {"command": "echo pwned"},
        {"argv": ["curl", "https://example.com"]},
        {"argv": [sys.executable, "-c", f"open({str(outside)!r},'w').write('pwned')"]},
    ]
    for attack in attacks:
        with pytest.raises(ToolError):
            tools.execute("process", attack)
    assert hashlib.sha256(outside.read_bytes()).hexdigest() == before


def test_verify_requires_external_admission_digest(tmp_path: Path) -> None:
    run, trusted = make_run(tmp_path)
    assert verify_run(run)["valid"] is False
    assert verify_run(run, trusted_suite_digest=trusted)["valid"] is True
    assert verify_run(run, trusted_suite_digest="0" * 64)["valid"] is False


@pytest.mark.parametrize("target,mutate", [
    ("suite.json", lambda d: d["tasks"][0].update(prompt="tampered")),
    ("result.json", lambda d: d["tasks"][0].update(passed=False)),
    ("manifest.json", lambda d: d.update(route_config_digest="0" * 64)),
])
def test_verify_rejects_tampered_bound_artifacts(tmp_path: Path, target: str, mutate) -> None:
    run, trusted = make_run(tmp_path)
    path = run / target; data = json.loads(path.read_text()); mutate(data); path.write_text(json.dumps(data))
    assert verify_run(run, trusted_suite_digest=trusted)["valid"] is False


def test_verify_rejects_workspace_tamper_missing_manifest_entry_and_unreconciled_receipt(tmp_path: Path) -> None:
    for mode in ("workspace", "missing", "receipt"):
        run, trusted = make_run(tmp_path / mode)
        if mode == "workspace":
            (run / "workspace" / "one" / "answer.txt").write_text("43")
        elif mode == "missing":
            p = run / "manifest.json"; d = json.loads(p.read_text()); d["artifact_digests"].pop("result.json"); p.write_text(json.dumps(d))
        else:
            with (run / "receipts.jsonl").open("a") as f: f.write("{}\n")
        assert verify_run(run, trusted_suite_digest=trusted)["valid"] is False


def test_result_has_complete_classification_and_integrity_fields_and_redacts_content(tmp_path: Path) -> None:
    run, trusted = make_run(tmp_path)
    result = json.loads((run / "result.json").read_text())
    expected = {"requested_route", "effective_route", "harness", "harness_version", "limits", "seed", "attempt",
                "started_at", "finished_at", "suite_digest", "fixture_hashes", "verifier_hashes", "expected_checks",
                "enumerated_checks", "passed_checks", "mutation_manifest", "immutable_after_hashes", "trace_hash",
                "output_hash", "verifier_receipt_hash", "route_config_digest", "receipt_chain_head"}
    assert expected <= result.keys()
    task = result["tasks"][0]
    assert {"semantic_status", "termination_status", "timeout_status", "provider_status", "budget_status",
            "evaluator_status"} <= task.keys()
    assert "final" not in task and "sensitive model response" not in (run / "result.json").read_text()
    assert verify_run(run, trusted_suite_digest=trusted)["valid"] is True


def test_write_is_anchored_when_ancestor_is_swapped_after_open(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "workspace"; root.mkdir()
    (root / "parent").mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    canary = outside / "answer.txt"; canary.write_text("unchanged")
    tools = ToolExecutor(root)
    real_open = os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == "parent" and dir_fd is not None and not swapped:
            swapped = True
            (root / "parent").rename(root / "detached")
            (root / "parent").symlink_to(outside, target_is_directory=True)
        return fd

    monkeypatch.setattr(os, "open", racing_open)
    tools.execute("write_file", {"path": "parent/answer.txt", "content": "safe"})
    assert canary.read_text() == "unchanged"
    assert (root / "detached" / "answer.txt").read_text() == "safe"


def _rehash_receipts(path: Path) -> None:
    previous = "0" * 64
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for sequence, row in enumerate(rows):
        row["sequence"] = sequence; row["previous_hash"] = previous
        core = {k: v for k, v in row.items() if k != "hash"}
        row["hash"] = hashlib.sha256(canonical(core)).hexdigest(); previous = row["hash"]
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


def test_verify_rejects_semantically_forged_and_rehashed_receipts(tmp_path: Path) -> None:
    run, trusted = make_run(tmp_path)
    path = run / "receipts.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        row["payload"] = {"forged": True}
    path.write_text("".join(json.dumps(row) + "\n" for row in rows)); _rehash_receipts(path)
    forged_rows = [json.loads(line) for line in path.read_text().splitlines()]
    result_path = run / "result.json"; result = json.loads(result_path.read_text())
    result["receipt_chain_head"] = forged_rows[-1]["hash"]
    result_path.write_bytes(canonical(result))
    manifest_path = run / "manifest.json"; manifest = json.loads(manifest_path.read_text())
    manifest["receipt_chain_head"] = forged_rows[-1]["hash"]
    manifest["artifact_digests"]["receipts.jsonl"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["result_digest"] = manifest["artifact_digests"]["result.json"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    manifest_path.write_bytes(canonical(manifest))
    assert verify_run(run, trusted_suite_digest=trusted)["valid"] is False


def test_schema_and_runtime_accept_every_shipped_suite_and_fixture_verifier() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads((root / "schemas/suite.schema.json").read_text())
    variants = schema["$defs"]["task"]["properties"]["verifier"]["oneOf"]
    assert any(v.get("properties", {}).get("type", {}).get("const") == "fixture" for v in variants)
    for path in (root / "suites").glob("*.json"):
        data = json.loads(path.read_text())
        if path.name == "heldout-generator.json":
            validate_suite_metadata(data)
        else:
            validate_suite(data)


def test_provenance_validator_rejects_stale_sha256(tmp_path: Path) -> None:
    material = tmp_path / "artifact.json"; material.write_text("original")
    (tmp_path / "PROVENANCE.json").write_text(json.dumps({"materials": [{"path": "artifact.json", "sha256": hashlib.sha256(material.read_bytes()).hexdigest()}]}))
    validate_provenance(tmp_path)
    material.write_text("tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_provenance(tmp_path)
