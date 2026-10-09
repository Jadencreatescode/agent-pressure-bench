from __future__ import annotations

import argparse
import json
import os
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from .adapters import FixtureAdapter, OpenAICompatibleAdapter
from .runner import BenchmarkRunner, RunConfig, digest_json
from .verification import verify_run
from .validation import validate_suite

SUITES = files("agent_pressure_bench").joinpath("suites")


def load_suite(name: str) -> dict[str, Any]:
    if not name.replace("-", "").isalnum(): raise ValueError("invalid suite name")
    path = SUITES.joinpath(f"{name}.json")
    if not path.is_file(): raise ValueError(f"unknown suite: {name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_suite(data)
    return data


def build_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("invalid aggregate report")
    rows = []
    for name in sorted(data):
        value = data[name]
        if isinstance(value, dict) and type(value.get("passed")) is int and type(value.get("total")) is int:
            total = value["total"]
            rows.append({"name": name, "passed": value["passed"], "total": total,
                         "rate": None if total == 0 else round(value["passed"] / total, 6)})
    return {"schema_version": "1.0", "rows": rows}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="apb", description="Agent Pressure Bench")
    subs = root.add_subparsers(dest="command", required=True)
    subs.add_parser("list", help="list public suites")
    run = subs.add_parser("run", help="run a suite")
    run.add_argument("suite"); run.add_argument("--adapter", choices=["fixture", "openai"], default="fixture")
    run.add_argument("--output", type=Path, default=Path("runs")); run.add_argument("--base-url", default=os.getenv("APB_BASE_URL"))
    run.add_argument("--model", default=os.getenv("APB_MODEL")); run.add_argument("--api-key-env", default="APB_API_KEY")
    verify = subs.add_parser("verify", help="independently verify a persisted run")
    verify.add_argument("run_dir", type=Path)
    verify.add_argument("--suite-digest", required=True,
                        help="externally trusted SHA-256 admission digest (never read from the run directory)")
    report = subs.add_parser("report", help="render a deterministic aggregate report")
    report.add_argument("input", type=Path); report.add_argument("--format", choices=["json"], default="json")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "list":
            for path in sorted(SUITES.glob("*.json")):
                if path.name != "heldout-generator.json":
                    data = json.loads(path.read_text()); print(f"{data['id']}\t{data['track']}\t{len(data['tasks'])}")
            return 0
        if args.command == "verify":
            report = verify_run(args.run_dir, trusted_suite_digest=args.suite_digest)
            print(json.dumps(report, sort_keys=True)); return 0 if report["valid"] else 1
        if args.command == "report":
            print(json.dumps(build_report(args.input), ensure_ascii=False, separators=(",", ":")))
            return 0
        suite = load_suite(args.suite)
        if args.adapter == "fixture": adapter = FixtureAdapter()
        else:
            if not args.base_url or not args.model: raise ValueError("--base-url and --model are required for openai adapter")
            adapter = OpenAICompatibleAdapter(args.base_url, args.model, os.getenv(args.api_key_env))
        trusted_digest = digest_json(suite)
        run_dir = BenchmarkRunner(adapter, RunConfig(
            args.output, requested_route=args.adapter,
            effective_route=(args.model if args.adapter == "openai" else "fixture"),
        )).run_suite(suite, admission_digest=trusted_digest)
        report = verify_run(run_dir, trusted_suite_digest=trusted_digest)
        print(json.dumps({"run_dir": str(run_dir.resolve()), **report["summary"], "verified": report["valid"]}, sort_keys=True))
        return 0 if report["valid"] and report["summary"]["failed"] == 0 else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"apb: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
