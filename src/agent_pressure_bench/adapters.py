from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class AdapterError(RuntimeError):
    pass


class Adapter(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class ScriptedAdapter:
    scripts: list[list[dict[str, Any]]]
    _task: int = 0
    _turn: int = 0

    def start_task(self, task: dict[str, Any]) -> None:
        self._turn = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if self._task >= len(self.scripts):
            raise AdapterError("no script available for task")
        script = self.scripts[self._task]
        if self._turn >= len(script):
            self._task += 1
            self._turn = 0
            raise AdapterError("script ended without final response")
        response = script[self._turn]
        self._turn += 1
        if not response.get("tool_calls"):
            self._task += 1
            self._turn = 0
        return {"content": response.get("content"), "tool_calls": response.get("tool_calls", [])}


class FixtureAdapter:
    """Smoke adapter that replays a fixture's sealed reference snapshot."""
    def __init__(self) -> None:
        self.responses: list[dict[str, Any]] = []

    def start_task(self, task: dict[str, Any]) -> None:
        fixture = task.get("fixture_response")
        verifier = task.get("verifier", {})
        if fixture is None and verifier.get("type") == "fixture":
            fixture = {"fixture_id": verifier["fixture_id"]}
        if not isinstance(fixture, dict):
            raise AdapterError("task has no replayable fixture")
        if "fixture_id" in fixture:
            from .fixtures import find_fixture
            work = find_fixture(fixture["fixture_id"]) / "reference_snapshot" / "work"
            candidates = [p for p in (work / "answer.json", work / "solution.py") if p.is_file()]
            if len(candidates) != 1:
                raise AdapterError("fixture reference snapshot must contain one candidate artifact")
            path = candidates[0]
            self.responses = [
                {"tool_calls": [{"id": "fixture-call", "name": "write_file", "arguments": {
                    "path": f"work/{path.name}", "content": path.read_text(encoding="utf-8")}}]},
                {"content": "done"},
            ]
        elif "tool" in fixture:
            self.responses = [
                {"tool_calls": [{"id": "fixture-call", "name": fixture["tool"], "arguments": fixture.get("arguments", {})}]},
                {"content": fixture.get("final", "done")},
            ]
        else:
            self.responses = [{"content": fixture.get("final")}]

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.responses:
            raise AdapterError("fixture response exhausted")
        response = self.responses.pop(0)
        return {"content": response.get("content"), "tool_calls": response.get("tool_calls", [])}


@dataclass
class OpenAICompatibleAdapter:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0
    temperature: float = 0.0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "temperature": self.temperature}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
            message = payload["choices"][0]["message"]
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AdapterError(f"OpenAI-compatible request failed: {exc}") from exc
        calls = []
        for call in message.get("tool_calls", []):
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError as exc:
                raise AdapterError("model returned invalid tool arguments JSON") from exc
            calls.append({"id": call.get("id", "call"), "name": function.get("name"), "arguments": arguments})
        return {"content": message.get("content"), "tool_calls": calls}
