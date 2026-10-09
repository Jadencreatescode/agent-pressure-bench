from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_public_suite_inventory_has_declared_cell_counts() -> None:
    expected = {"bounded": 24, "long-horizon": 9, "heldout-samples": 9, "failure-edge": 18,
                "progressive-reasoning": 17, "executable-coding": 24}
    for name, count in expected.items():
        suite = json.loads((ROOT / "suites" / f"{name}.json").read_text())
        assert len(suite["tasks"]) == count
        ids = [task["id"] for task in suite["tasks"]]
        assert len(ids) == len(set(ids))
        for task in suite["tasks"]:
            assert task["budget"] >= 0
            assert task["verifier"]["type"] in {"file_equals", "final_equals", "json_schema", "fixture"}


def test_reference_aggregate_is_sanitized_and_caveated() -> None:
    data = json.loads((ROOT / "results" / "agent-max-2-reference-aggregate.json").read_text())
    assert data["bounded"]["passed"] == 24
    assert data["long_horizon_frozen"]["passed"] == 9
    assert data["held_out"]["passed"] == 9
    assert data["bridge_arex"]["exact_dflash_parity"] is False
    text = json.dumps(data)
    assert "/Users/" not in text and "/home/" not in text


def test_json_schemas_are_valid_json_and_require_versions() -> None:
    for path in (ROOT / "schemas").glob("*.json"):
        schema = json.loads(path.read_text())
        assert schema["$schema"].startswith("https://json-schema.org/")
        assert "schema_version" in schema.get("required", [])


def test_draft_2020_12_schemas_validate_all_twelve_public_documents() -> None:
    from jsonschema import Draft202012Validator

    suite_schema = json.loads((ROOT / "schemas" / "suite.schema.json").read_text())
    metadata_schema = json.loads((ROOT / "schemas" / "heldout-generator.schema.json").read_text())
    Draft202012Validator.check_schema(suite_schema)
    Draft202012Validator.check_schema(metadata_schema)
    documents = sorted((ROOT / "suites").glob("*.json"))
    assert len(documents) == 12
    for path in documents:
        schema = metadata_schema if path.name == "heldout-generator.json" else suite_schema
        Draft202012Validator(schema).validate(json.loads(path.read_text()))


def test_all_public_suites_are_admitted_and_package_copies_match() -> None:
    from agent_pressure_bench.validation import validate_suite, validate_suite_metadata
    package_suites = ROOT / "src" / "agent_pressure_bench" / "suites"
    source_paths = sorted((ROOT / "suites").glob("*.json"))
    assert len(source_paths) == 12
    total = 0
    ids = set()
    for path in source_paths:
        data = json.loads(path.read_text())
        assert (package_suites / path.name).read_bytes() == path.read_bytes()
        if path.name == "heldout-generator.json":
            validate_suite_metadata(data)
            continue
        validate_suite(data)
        assert data["id"] not in ids; ids.add(data["id"]); total += len(data["tasks"])
    assert len(ids) == 11
    assert total == 108
