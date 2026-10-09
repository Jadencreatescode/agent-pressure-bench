#!/usr/bin/env python3
"""Build oracle-free public suite indexes for tranche-2 fixtures."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures" / "tranche2"


def emit(name: str, track: str, description: str, tasks: list[dict]) -> None:
    data = {"schema_version": "1.0", "id": name, "track": track, "description": description,
            "license": "Apache-2.0", "tasks": tasks}
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    (ROOT / "suites" / f"{name}.json").write_text(raw)
    (ROOT / "src" / "agent_pressure_bench" / "suites" / f"{name}.json").write_text(raw)


def task(fixture_id: str, family: str, difficulty: int, *, budget: int = 4,
         task_id: str | None = None, prompt_suffix: str = "") -> dict:
    root = FIXTURES / fixture_id
    manifest = json.loads((root / "manifest.json").read_text())
    prompt = (root / "prompt.md").read_text().rstrip()
    prompt += "\n\nThe fixture inputs are materialized in your current workspace. Use read_file and write_file; do not access repository fixture paths."
    if prompt_suffix:
        prompt += " " + prompt_suffix
    return {
        "id": task_id or fixture_id.lower().replace("-", "_"),
        "family": family,
        "difficulty": difficulty,
        "prompt": prompt + "\n",
        "budget": budget,
        "verifier": {"type": "fixture", "fixture_id": fixture_id,
                     "expected_checks": manifest["expected_checks"]},
    }


reasoning = [task(f"R{i:02d}", "deductive_reasoning", i) for i in range(1, 18)]
emit("progressive-reasoning", "reasoning", "Seventeen externally verified reasoning fixtures with strict answer/evidence envelopes.", reasoning)

coding = [task(f"C{i:02d}-v{v}", "executable_coding", i, budget=8)
          for i in range(1, 9) for v in range(1, 4)]
emit("executable-coding", "executable_coding", "Twenty-four source-repair fixtures executed by verifier-owned contract subprocesses.", coding)

for name, track, fixture_id, family in (
    ("structured-output", "structured_output", "S01", "structured_json"),
    ("safety", "safety", "S02", "confinement"),
    ("vision-format", "vision_request_format", "S04", "synthetic_vision"),
    ("harness-contract", "harness_comparison", "S05", "trace_comparison"),
):
    emit(name, track, f"Externally verified {fixture_id} synthetic fixture.",
         [task(fixture_id, family, 1)])

emit("long-context", "long_context", "Deterministic large-corpus retrieval at three declared context budgets.", [
    task("S03", "retrieval", i, task_id=f"s03_{label}",
         prompt_suffix=f"Declared context budget: {label}.")
    for i, label in enumerate(("60k", "80k", "100k"), 1)
])
print("updated oracle-free tranche-2 suite indexes and package copies")
