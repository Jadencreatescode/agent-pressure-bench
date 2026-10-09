from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SUITE_KEYS = {"schema_version", "id", "track", "description", "license", "tasks"}
_METADATA_KEYS = {"schema_version", "id", "track", "algorithm", "note", "public_seed", "sample_count"}
_TASK_KEYS = {"id", "family", "difficulty", "prompt", "budget", "verifier", "fixture_response"}
_VERIFIER_KEYS = {
    "file_equals": {"type", "path", "value"},
    "final_equals": {"type", "value"},
    "json_schema": {"type", "required"},
    "fixture": {"type", "fixture_id", "expected_checks"},
}


def _plain_int(value: Any) -> bool:
    return type(value) is int


def validate_provenance(root: Path) -> None:
    """Verify that every provenance record names the exact bytes on disk."""
    document = json.loads((root / "PROVENANCE.json").read_text(encoding="utf-8"))
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise ValueError("provenance materials must be an array")
    for record in materials:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("invalid provenance material record")
        path = root / record["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if record.get("sha256") != actual:
            raise ValueError(f"SHA-256 mismatch: {record['path']}")


def validate_suite(data: Any) -> None:
    """Fail-closed admission checks for public suite documents."""
    if not isinstance(data, dict) or set(data) - _SUITE_KEYS:
        raise ValueError("suite must be an object with only supported fields")
    required = {"schema_version", "id", "track", "tasks"}
    if not required <= set(data) or data["schema_version"] != "1.0" or type(data["schema_version"]) is not str:
        raise ValueError("unsupported or missing suite schema_version")
    if not isinstance(data["id"], str) or not _ID.fullmatch(data["id"]):
        raise ValueError("invalid suite id")
    if not isinstance(data["track"], str) or not data["track"]:
        raise ValueError("invalid suite track")
    tasks = data["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("suite tasks must be a non-empty array")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) - _TASK_KEYS:
            raise ValueError("task contains unsupported fields")
        if not {"id", "family", "difficulty", "prompt", "budget", "verifier"} <= set(task):
            raise ValueError("task is missing required fields")
        task_id = task["id"]
        if not isinstance(task_id, str) or not _ID.fullmatch(task_id) or task_id in seen:
            raise ValueError("task ids must be valid and unique")
        seen.add(task_id)
        if not isinstance(task["family"], str) or not task["family"]:
            raise ValueError("invalid task family")
        if not isinstance(task["prompt"], str) or not task["prompt"]:
            raise ValueError("invalid task prompt")
        if not _plain_int(task["difficulty"]) or task["difficulty"] < 1:
            raise ValueError("difficulty must be a positive integer")
        if not _plain_int(task["budget"]) or task["budget"] < 0:
            raise ValueError("budget must be a non-negative integer")
        verifier = task["verifier"]
        if not isinstance(verifier, dict) or verifier.get("type") not in _VERIFIER_KEYS:
            raise ValueError("unsupported verifier")
        if set(verifier) != _VERIFIER_KEYS[verifier["type"]]:
            raise ValueError("verifier fields do not match its type")
        if verifier["type"] == "file_equals":
            path = verifier["path"]
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
                raise ValueError("invalid verifier path")
        elif verifier["type"] == "json_schema":
            if not isinstance(verifier["required"], list) or not all(isinstance(x, str) for x in verifier["required"]):
                raise ValueError("json_schema required must be a string array")
        elif verifier["type"] == "fixture":
            if (not isinstance(verifier["fixture_id"], str) or not _ID.fullmatch(verifier["fixture_id"].lower())
                    or not _plain_int(verifier["expected_checks"]) or verifier["expected_checks"] <= 0):
                raise ValueError("invalid fixture verifier")
        fixture = task.get("fixture_response")
        if fixture is not None and not isinstance(fixture, dict):
            raise ValueError("fixture_response must be an object")


def validate_suite_metadata(data: Any) -> None:
    """Validate a non-runnable suite metadata document."""
    if not isinstance(data, dict) or set(data) != _METADATA_KEYS:
        raise ValueError("suite metadata fields do not match the metadata contract")
    if data["schema_version"] != "1.0" or type(data["schema_version"]) is not str:
        raise ValueError("unsupported metadata schema_version")
    if data["id"] != "heldout-generator" or data["track"] != "heldout_generator":
        raise ValueError("invalid suite metadata identity")
    for key in ("algorithm", "note", "public_seed"):
        if not isinstance(data[key], str) or not data[key]:
            raise ValueError(f"invalid metadata {key}")
    if not _plain_int(data["sample_count"]) or data["sample_count"] <= 0:
        raise ValueError("metadata sample_count must be a positive integer")
