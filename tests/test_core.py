from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agent_pressure_bench.adapters import OpenAICompatibleAdapter, ScriptedAdapter
from agent_pressure_bench.receipts import ReceiptChain, verify_receipt_chain
from agent_pressure_bench.runner import BenchmarkRunner, RunConfig, digest_json
from agent_pressure_bench.validation import validate_suite
from agent_pressure_bench.tools import ToolError, ToolExecutor
from agent_pressure_bench.verification import verify_run


def test_tool_executor_confines_paths_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (root / "link").symlink_to(outside)
    tools = ToolExecutor(root)
    tools.execute("write_file", {"path": "ok.txt", "content": "hello"})
    assert (root / "ok.txt").read_text() == "hello"
    with pytest.raises(ToolError):
        tools.execute("read_file", {"path": "../outside.txt"})
    with pytest.raises(ToolError):
        tools.execute("read_file", {"path": "link"})


def test_process_tool_is_disabled_by_default(tmp_path: Path) -> None:
    tools = ToolExecutor(tmp_path)
    with pytest.raises(ToolError):
        tools.execute("process", {"argv": [sys.executable, "-c", "print('unsafe')"]})


def test_receipt_chain_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    chain = ReceiptChain(path)
    chain.append("run_started", {"run_id": "synthetic"})
    chain.append("run_finished", {"passed": True})
    assert verify_receipt_chain(path)["valid"] is True
    rows = path.read_text().splitlines()
    altered = json.loads(rows[1])
    altered["payload"]["passed"] = False
    rows[1] = json.dumps(altered, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(rows) + "\n")
    assert verify_receipt_chain(path)["valid"] is False


def test_runner_native_multiturn_budget_and_persisted_verification(tmp_path: Path) -> None:
    suite = {
        "schema_version": "1.0",
        "id": "smoke",
        "track": "bounded",
        "tasks": [{
            "id": "write-answer",
            "family": "filesystem",
            "difficulty": 1,
            "prompt": "Write answer.txt containing 42, then finish.",
            "budget": 2,
            "verifier": {"type": "file_equals", "path": "answer.txt", "value": "42"},
        }],
    }
    adapter = ScriptedAdapter([[{
        "tool_calls": [{"id": "c1", "name": "write_file", "arguments": {"path": "answer.txt", "content": "42"}}]
    }, {"content": "done"}]])
    run_dir = BenchmarkRunner(adapter, RunConfig(output_root=tmp_path / "runs")).run_suite(suite)
    persisted = verify_run(run_dir, trusted_suite_digest=digest_json(suite))
    assert persisted["valid"] is True
    assert persisted["summary"]["passed"] == 1
    assert persisted["summary"]["executed_tool_calls"] == 1


def test_budget_is_hard_limit(tmp_path: Path) -> None:
    suite = {"schema_version": "1.0", "id": "budget", "track": "bounded", "tasks": [{
        "id": "too-many", "family": "budget", "difficulty": 1, "prompt": "test", "budget": 1,
        "verifier": {"type": "final_equals", "value": "never"},
    }]}
    adapter = ScriptedAdapter([[{
        "tool_calls": [
            {"id": "a", "name": "write_file", "arguments": {"path": "a", "content": "a"}},
            {"id": "b", "name": "write_file", "arguments": {"path": "b", "content": "b"}},
        ]
    }]])
    run_dir = BenchmarkRunner(adapter, RunConfig(output_root=tmp_path / "runs")).run_suite(suite)
    result = json.loads((run_dir / "result.json").read_text())
    assert result["tasks"][0]["status"] == "budget_exhausted"
    assert not (run_dir / "workspace" / "too-many" / "b").exists()


def test_openai_adapter_constructs_nonstreaming_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = OpenAICompatibleAdapter("https://api.example.com/v1", "model", api_key="test-key")
    assert adapter.complete([{"role": "user", "content": "hi"}], []) == {"content": "ok", "tool_calls": []}
    assert captured["body"]["stream"] is False
    assert captured["body"]["model"] == "model"


def test_openai_adapter_uses_real_local_http_server() -> None:
    received = {}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            received["path"] = self.path
            received["body"] = json.loads(self.rfile.read(length))
            payload = json.dumps({"choices": [{"message": {"content": "LOCAL_OK"}}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
        def log_message(self, format, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        adapter = OpenAICompatibleAdapter(f"http://127.0.0.1:{server.server_port}/v1", "local-model")
        assert adapter.complete([{"role": "user", "content": "hello"}], [])["content"] == "LOCAL_OK"
    finally:
        server.shutdown(); thread.join(); server.server_close()
    assert received["path"] == "/v1/chat/completions"
    assert received["body"]["model"] == "local-model"


def test_suite_admission_rejects_unknown_fields_duplicate_ids_and_bad_verifier() -> None:
    base = {"schema_version": "1.0", "id": "valid", "track": "bounded", "license": "Apache-2.0",
            "description": "Synthetic.", "tasks": [{"id": "one", "family": "x", "difficulty": 1,
            "prompt": "p", "budget": 1, "verifier": {"type": "final_equals", "value": "ok"}}]}
    validate_suite(base)
    for mutate in (
        lambda d: d.update(extra=True),
        lambda d: d["tasks"].append(dict(d["tasks"][0])),
        lambda d: d["tasks"][0].update(verifier={"type": "unknown"}),
        lambda d: d.update(schema_version=True),
    ):
        candidate = json.loads(json.dumps(base)); mutate(candidate)
        with pytest.raises(ValueError): validate_suite(candidate)


def test_independent_verifier_subprocess_detects_tamper(tmp_path: Path) -> None:
    suite = {"schema_version": "1.0", "id": "verify", "track": "bounded", "license": "Apache-2.0",
             "description": "Synthetic.", "tasks": [{"id": "one", "family": "x", "difficulty": 1,
             "prompt": "p", "budget": 0, "verifier": {"type": "final_equals", "value": "ok"},
             "fixture_response": {"final": "ok"}}]}
    run_dir = BenchmarkRunner(__import__("agent_pressure_bench.adapters", fromlist=["FixtureAdapter"]).FixtureAdapter(),
                              RunConfig(tmp_path / "runs")).run_suite(suite)
    trusted = digest_json(suite)
    clean = subprocess.run([sys.executable, "-m", "agent_pressure_bench", "verify", str(run_dir),
                            "--suite-digest", trusted], text=True, capture_output=True)
    assert clean.returncode == 0, clean.stderr
    result = json.loads((run_dir / "result.json").read_text()); result["summary"]["passed"] = 0
    (run_dir / "result.json").write_text(json.dumps(result))
    bad = subprocess.run([sys.executable, "-m", "agent_pressure_bench", "verify", str(run_dir),
                          "--suite-digest", trusted], text=True, capture_output=True)
    assert bad.returncode == 1


def test_report_command_is_deterministic(tmp_path: Path) -> None:
    fixture = tmp_path / "aggregate.json"
    fixture.write_text(json.dumps({"schema_version": "1.0", "b": {"passed": 1, "total": 2},
                                   "a": {"passed": 2, "total": 2}}))
    command = [sys.executable, "-m", "agent_pressure_bench", "report", str(fixture), "--format", "json"]
    first = subprocess.run(command, text=True, capture_output=True)
    second = subprocess.run(command, text=True, capture_output=True)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert list(json.loads(first.stdout)["rows"][0]) == ["name", "passed", "total", "rate"]


def test_cli_lists_and_runs_packaged_suite(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    listed = subprocess.run([sys.executable, "-m", "agent_pressure_bench", "list"], env=env, text=True, capture_output=True)
    assert listed.returncode == 0, listed.stderr
    assert "bounded" in listed.stdout
    run = subprocess.run([
        sys.executable, "-m", "agent_pressure_bench", "run", "structured-output",
        "--adapter", "fixture", "--output", str(tmp_path / "runs")
    ], env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["passed"] == payload["total"]
