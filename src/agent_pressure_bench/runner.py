from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .receipts import ReceiptChain
from .tools import TOOL_SCHEMAS, SandboxAdapter, ToolError, ToolExecutor, sandbox_tool_schema
from .validation import validate_suite
from .fixtures import find_fixture, materialize_fixture, verify_fixture

HARNESS_VERSION = "1.1.0"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return sha256_bytes(canonical(value))


def evaluate(verifier: dict[str, Any], workspace: Path, final: str | None) -> tuple[bool, str]:
    kind = verifier.get("type")
    if kind == "file_equals":
        rel = verifier.get("path")
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            return False, "invalid verifier path"
        path = workspace / rel
        try:
            resolved = path.resolve(strict=True)
            root = workspace.resolve(strict=True)
        except OSError:
            return False, "expected file missing"
        if (resolved != root and root not in resolved.parents) or path.is_symlink() or not path.is_file():
            return False, "expected file missing"
        return path.read_text(encoding="utf-8") == verifier.get("value"), "file equality"
    if kind == "final_equals":
        return final == verifier.get("value"), "final equality"
    if kind == "json_schema":
        try:
            value = json.loads(final or "")
        except json.JSONDecodeError:
            return False, "invalid JSON"
        required = verifier.get("required", [])
        return isinstance(value, dict) and all(key in value for key in required), "required JSON keys"
    if kind == "fixture":
        result = verify_fixture(find_fixture(verifier["fixture_id"]), workspace)
        counts_match = (result.get("expected_checks") == verifier["expected_checks"] ==
                        result.get("enumerated_checks") == result.get("reported_checks"))
        return bool(result.get("passed")) and counts_match and result.get("process_returncode") == 0, "external fixture verifier"
    return False, f"unknown verifier: {kind}"


def workspace_manifest(workspace_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not workspace_root.exists():
        return result
    for path in sorted(workspace_root.rglob("*")):
        if path.is_symlink():
            result[str(path.relative_to(workspace_root))] = "SYMLINK_REJECTED"
        elif path.is_file():
            result[str(path.relative_to(workspace_root))] = sha256_bytes(path.read_bytes())
    return result


def output_evidence(verifier: dict[str, Any], final: str | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {"present": final is not None, "sha256": sha256_bytes((final or "").encode())}
    if verifier.get("type") == "json_schema":
        try:
            value = json.loads(final or "")
            evidence["json_object_keys"] = sorted(value) if isinstance(value, dict) else None
        except json.JSONDecodeError:
            evidence["json_object_keys"] = None
    return evidence


@dataclass(frozen=True)
class RunConfig:
    output_root: Path
    max_turns: int = 32
    requested_route: str = "default"
    effective_route: str = "default"
    seed: int = 0
    attempt: int = 1
    timeout_seconds: float = 60.0
    sandbox_adapter: SandboxAdapter | None = None


class BenchmarkRunner:
    def __init__(self, adapter: Any, config: RunConfig):
        self.adapter, self.config = adapter, config

    def run_suite(self, suite: dict[str, Any], *, admission_digest: str | None = None) -> Path:
        validate_suite(suite)
        suite_digest = digest_json(suite)
        if admission_digest is not None and admission_digest != suite_digest:
            raise ValueError("suite does not match externally supplied admission digest")
        run_id = uuid.uuid4().hex
        run_dir = self.config.output_root / run_id
        run_dir.mkdir(parents=True)
        started_at = datetime.now(timezone.utc).isoformat()
        (run_dir / "suite.json").write_bytes(canonical(suite))
        receipts = ReceiptChain(run_dir / "receipts.jsonl")
        route = {"requested": self.config.requested_route, "effective": self.config.effective_route}
        route_digest = digest_json(route)
        receipts.append("run_started", {"run_id": run_id, "suite_id": suite["id"], "suite_digest": suite_digest,
                                         "route_config_digest": route_digest})
        results: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        verifier_receipt_hash = "0" * 64
        tools_schema = TOOL_SCHEMAS + ([sandbox_tool_schema()] if self.config.sandbox_adapter else [])
        for task in suite["tasks"]:
            workspace = run_dir / "workspace" / task["id"]
            workspace.mkdir(parents=True)
            if task["verifier"]["type"] == "fixture":
                materialize_fixture(find_fixture(task["verifier"]["fixture_id"]), workspace)
            if hasattr(self.adapter, "start_task"):
                self.adapter.start_task(task)
            messages: list[dict[str, Any]] = [{"role": "user", "content": task["prompt"]}]
            executed, termination, final = 0, "max_turns", None
            provider_status, budget_status, timeout_status = "ok", "within_limit", "not_timed_out"
            for _ in range(self.config.max_turns):
                try:
                    response = self.adapter.complete(messages, tools_schema)
                except Exception as exc:
                    provider_status = "error"
                    trace.append({"task_id": task["id"], "provider_error_type": type(exc).__name__})
                    termination = "provider_error"
                    break
                calls = response.get("tool_calls", [])
                final = response.get("content")
                if not calls:
                    termination = "completed"
                    break
                messages.append({"role": "assistant", "content": final, "tool_calls": calls})
                for call in calls:
                    if executed >= int(task["budget"]):
                        budget_status, termination = "exhausted", "budget_exhausted"
                        break
                    executed += 1
                    try:
                        output = ToolExecutor(workspace, sandbox=self.config.sandbox_adapter).execute(call["name"], call.get("arguments", {}))
                    except ToolError as exc:
                        output = {"ok": False, "error": str(exc)}
                    event = {"task_id": task["id"], "ordinal": executed, "tool": call["name"], "ok": output.get("ok", False)}
                    receipts.append("tool_executed", event); trace.append(event)
                    messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(output)})
                if budget_status == "exhausted":
                    break
            passed, detail = evaluate(task["verifier"], workspace, final)
            evaluator_status = "passed" if passed else "failed"
            if termination != "completed":
                passed, evaluator_status = False, "not_evaluated" if provider_status != "ok" else "failed"
            evidence = output_evidence(task["verifier"], final)
            record = {
                "task_id": task["id"], "family": task["family"], "difficulty": task["difficulty"],
                "status": termination, "semantic_status": "passed" if passed else "failed",
                "termination_status": termination, "timeout_status": timeout_status, "provider_status": provider_status,
                "budget_status": budget_status, "evaluator_status": evaluator_status, "passed": passed,
                "verification": detail, "executed_tool_calls": executed, "budget": task["budget"],
                "output_evidence": evidence,
                "external_checks": task["verifier"].get("expected_checks", 0) if task["verifier"].get("type") == "fixture" else 0,
            }
            results.append(record)
            verifier_receipt_hash = receipts.append("task_finished", record)["hash"]
        summary = {"total": len(results), "passed": sum(r["passed"] for r in results),
                   "failed": sum(not r["passed"] for r in results),
                   "executed_tool_calls": sum(r["executed_tool_calls"] for r in results)}
        mutation_manifest = workspace_manifest(run_dir / "workspace")
        finished = receipts.append("run_finished", {**summary, "workspace_digest": digest_json(mutation_manifest)})
        finished_at = datetime.now(timezone.utc).isoformat()
        fixture_hashes = {t["id"]: digest_json(t["fixture_response"]) for t in suite["tasks"] if "fixture_response" in t}
        verifier_hashes = {t["id"]: digest_json(t["verifier"]) for t in suite["tasks"]}
        result = {
            "schema_version": "1.1", "run_id": run_id, "suite_id": suite["id"], "requested_route": route["requested"],
            "effective_route": route["effective"], "harness": "agent-pressure-bench", "harness_version": HARNESS_VERSION,
            "limits": {"max_turns": self.config.max_turns, "timeout_seconds": self.config.timeout_seconds,
                       "tool_budgets": {t["id"]: t["budget"] for t in suite["tasks"]}},
            "seed": self.config.seed, "attempt": self.config.attempt, "started_at": started_at, "finished_at": finished_at,
            "suite_digest": suite_digest, "fixture_hashes": fixture_hashes, "verifier_hashes": verifier_hashes,
            "expected_checks": len(suite["tasks"]), "enumerated_checks": len(results), "passed_checks": summary["passed"],
            "tasks": results, "summary": summary, "mutation_manifest": mutation_manifest,
            "immutable_after_hashes": dict(mutation_manifest), "trace_hash": digest_json(trace),
            "output_hash": digest_json({r["task_id"]: r["output_evidence"]["sha256"] for r in results}),
            "verifier_receipt_hash": verifier_receipt_hash, "route_config_digest": route_digest,
            "receipt_chain_head": finished["hash"],
            "metrics": {"tool_calls_per_second": None, "tokens_per_second": None},
        }
        (run_dir / "result.json").write_bytes(canonical(result))
        artifacts = {name: sha256_bytes((run_dir / name).read_bytes()) for name in ("suite.json", "result.json", "receipts.jsonl")}
        manifest = {"schema_version": "1.1", "suite_digest": suite_digest, "verifier_digest": digest_json(verifier_hashes),
                    "result_digest": artifacts["result.json"], "workspace_snapshot_digest": digest_json(mutation_manifest),
                    "mutation_manifest_digest": digest_json(mutation_manifest), "route_config_digest": route_digest,
                    "receipt_chain_head": finished["hash"], "artifact_digests": artifacts}
        (run_dir / "manifest.json").write_bytes(canonical(manifest))
        return run_dir
