from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .receipts import verify_receipt_chain
from .runner import digest_json, evaluate, workspace_manifest

_HEX = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_KEYS = {"schema_version", "suite_digest", "verifier_digest", "result_digest", "workspace_snapshot_digest",
                  "mutation_manifest_digest", "route_config_digest", "receipt_chain_head", "artifact_digests"}
_ARTIFACTS = {"suite.json", "result.json", "receipts.jsonl"}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _receipt_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("receipt must be an object")
        rows.append(row)
    return rows


def verify_run(run_dir: Path, trusted_suite_digest: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    summary: dict[str, Any] = {}
    chain: dict[str, Any] = {"valid": False, "count": 0}
    if trusted_suite_digest is None or not _HEX.fullmatch(trusted_suite_digest):
        return {"valid": False, "errors": ["a valid externally supplied trusted suite/admission digest is required"],
                "summary": {}, "receipt_chain": chain}
    try:
        manifest = _load_object(run_dir / "manifest.json")
        if set(manifest) != _MANIFEST_KEYS:
            errors.append("manifest fields are incomplete or unsupported")
        artifacts = manifest.get("artifact_digests")
        if not isinstance(artifacts, dict) or set(artifacts) != _ARTIFACTS:
            errors.append("artifact manifest must enumerate exactly all required artifacts")
            artifacts = {}
        for name in sorted(_ARTIFACTS):
            path = run_dir / name
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if artifacts.get(name) != actual:
                errors.append(f"digest mismatch: {name}")
        suite = _load_object(run_dir / "suite.json")
        stored = _load_object(run_dir / "result.json")
        actual_suite_digest = digest_json(suite)
        if actual_suite_digest != trusted_suite_digest:
            errors.append("suite does not match trusted admission digest")
        if manifest.get("suite_digest") != trusted_suite_digest or stored.get("suite_digest") != trusted_suite_digest:
            errors.append("suite digest binding mismatch")
        if manifest.get("result_digest") != hashlib.sha256((run_dir / "result.json").read_bytes()).hexdigest():
            errors.append("result digest binding mismatch")
        verifier_hashes = {t["id"]: digest_json(t["verifier"]) for t in suite["tasks"]}
        if stored.get("verifier_hashes") != verifier_hashes or manifest.get("verifier_digest") != digest_json(verifier_hashes):
            errors.append("verifier digest binding mismatch")
        route_digest = digest_json({"requested": stored.get("requested_route"), "effective": stored.get("effective_route")})
        if stored.get("route_config_digest") != route_digest or manifest.get("route_config_digest") != route_digest:
            errors.append("route config digest binding mismatch")
        current_workspace = workspace_manifest(run_dir / "workspace")
        workspace_digest = digest_json(current_workspace)
        if stored.get("mutation_manifest") != current_workspace or stored.get("immutable_after_hashes") != current_workspace:
            errors.append("workspace mutation manifest mismatch")
        if manifest.get("workspace_snapshot_digest") != workspace_digest or manifest.get("mutation_manifest_digest") != workspace_digest:
            errors.append("workspace digest binding mismatch")
        chain = verify_receipt_chain(run_dir / "receipts.jsonl")
        if not chain.get("valid"):
            errors.append("invalid receipt chain")
        if chain.get("head") != manifest.get("receipt_chain_head") or chain.get("head") != stored.get("receipt_chain_head"):
            errors.append("receipt chain head binding mismatch")
        rows = _receipt_rows(run_dir / "receipts.jsonl")
        tasks = stored.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("result tasks must be an array")
        by_id = {r.get("task_id"): r for r in tasks if isinstance(r, dict)}
        if len(by_id) != len(tasks) or set(by_id) != {t["id"] for t in suite["tasks"]}:
            errors.append("result task enumeration mismatch")
        recomputed = []
        for task in suite["tasks"]:
            prior = by_id.get(task["id"], {})
            verifier = task["verifier"]
            if verifier["type"] == "file_equals":
                passed, detail = evaluate(verifier, run_dir / "workspace" / task["id"], None)
            elif verifier["type"] == "final_equals":
                expected_hash = hashlib.sha256(str(verifier.get("value", "")).encode()).hexdigest()
                passed, detail = prior.get("output_evidence", {}).get("sha256") == expected_hash, "final equality"
            elif verifier["type"] == "json_schema":
                keys = prior.get("output_evidence", {}).get("json_object_keys")
                passed, detail = isinstance(keys, list) and all(k in keys for k in verifier.get("required", [])), "required JSON keys"
            else:
                passed, detail = evaluate(verifier, run_dir / "workspace" / task["id"], None)
            passed = passed and prior.get("termination_status") == "completed"
            if bool(prior.get("passed")) != passed or prior.get("semantic_status") != ("passed" if passed else "failed"):
                errors.append(f"task verdict mismatch: {task['id']}")
            recomputed.append({**prior, "passed": passed, "verification": detail})
        summary = {"total": len(recomputed), "passed": sum(bool(r.get("passed")) for r in recomputed),
                   "failed": sum(not bool(r.get("passed")) for r in recomputed),
                   "executed_tool_calls": sum(int(r.get("executed_tool_calls", 0)) for r in recomputed)}
        if summary != stored.get("summary"):
            errors.append("summary mismatch")
        if stored.get("expected_checks") != len(suite["tasks"]) or stored.get("enumerated_checks") != len(tasks) or stored.get("passed_checks") != summary["passed"]:
            errors.append("check counts mismatch")

        # A valid hash chain proves only byte integrity. Reconcile the complete
        # event language against independently bound suite/result state.
        expected_start = {"run_id": stored.get("run_id"), "suite_id": suite.get("id"),
                          "suite_digest": trusted_suite_digest, "route_config_digest": route_digest}
        cursor = 0
        receipt_shape = {"schema_version", "sequence", "timestamp", "event", "payload", "previous_hash", "hash"}
        semantic_ok = True
        if not rows or set(rows[0]) != receipt_shape or rows[0].get("event") != "run_started" or rows[0].get("payload") != expected_start:
            semantic_ok = False
        else:
            cursor = 1
        trace_events: list[dict[str, Any]] = []
        last_task_hash: str | None = None
        for suite_task in suite["tasks"]:
            record = by_id.get(suite_task["id"], {})
            count = record.get("executed_tool_calls")
            if type(count) is not int or count < 0 or count > suite_task["budget"]:
                semantic_ok = False
                count = 0
            for ordinal in range(1, count + 1):
                if cursor >= len(rows):
                    semantic_ok = False
                    break
                row = rows[cursor]
                payload = row.get("payload")
                if (set(row) != receipt_shape or row.get("event") != "tool_executed" or
                        not isinstance(payload, dict) or set(payload) != {"task_id", "ordinal", "tool", "ok"} or
                        payload.get("task_id") != suite_task["id"] or payload.get("ordinal") != ordinal or
                        not isinstance(payload.get("tool"), str) or type(payload.get("ok")) is not bool):
                    semantic_ok = False
                else:
                    trace_events.append(payload)
                cursor += 1
            if cursor >= len(rows):
                semantic_ok = False
                continue
            row = rows[cursor]
            if set(row) != receipt_shape or row.get("event") != "task_finished" or row.get("payload") != record:
                semantic_ok = False
            else:
                last_task_hash = row.get("hash")
            cursor += 1
        finish_payload = {**summary, "workspace_digest": workspace_digest}
        if (cursor != len(rows) - 1 or cursor < 0 or cursor >= len(rows) or set(rows[cursor]) != receipt_shape or
                rows[cursor].get("event") != "run_finished" or rows[cursor].get("payload") != finish_payload):
            semantic_ok = False
        if not semantic_ok:
            errors.append("receipt semantics do not reconcile with suite and result")
        if stored.get("verifier_receipt_hash") != last_task_hash:
            errors.append("verifier receipt hash mismatch")
        if stored.get("trace_hash") != digest_json(trace_events):
            errors.append("trace digest mismatch")
        output_hash = digest_json({r.get("task_id"): r.get("output_evidence", {}).get("sha256") for r in tasks})
        if stored.get("output_hash") != output_hash:
            errors.append("output digest mismatch")
        if stored.get("suite_id") != suite.get("id"):
            errors.append("suite id mismatch")
        fixture_hashes = {t["id"]: digest_json(t["fixture_response"]) for t in suite["tasks"] if "fixture_response" in t}
        if stored.get("fixture_hashes") != fixture_hashes:
            errors.append("fixture digest binding mismatch")
        required_result = {"schema_version", "run_id", "suite_id", "requested_route", "effective_route", "harness",
                           "harness_version", "limits", "seed", "attempt", "started_at", "finished_at", "suite_digest",
                           "fixture_hashes", "verifier_hashes", "expected_checks", "enumerated_checks", "passed_checks",
                           "tasks", "summary", "mutation_manifest", "immutable_after_hashes", "trace_hash", "output_hash",
                           "verifier_receipt_hash", "route_config_digest", "receipt_chain_head", "metrics"}
        if set(stored) != required_result:
            errors.append("result fields are incomplete or unsupported")
        return {"valid": not errors, "errors": errors, "summary": summary, "receipt_chain": chain}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return {"valid": False, "errors": errors, "summary": summary, "receipt_chain": chain}
