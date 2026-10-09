from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class ReceiptChain:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.previous = GENESIS
        self.sequence = 0

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        core = {"schema_version": "1.0", "sequence": self.sequence, "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event, "payload": payload, "previous_hash": self.previous}
        row = {**core, "hash": hashlib.sha256(_canonical(core)).hexdigest()}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(row).decode("utf-8") + "\n")
            handle.flush(); __import__("os").fsync(handle.fileno())
        self.previous = row["hash"]
        self.sequence += 1
        return row


def verify_receipt_chain(path: Path) -> dict[str, Any]:
    previous, count = GENESIS, 0
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                claimed = row.pop("hash")
                if row.get("sequence") != count or row.get("previous_hash") != previous:
                    return {"valid": False, "count": count, "error": "sequence or link mismatch"}
                actual = hashlib.sha256(_canonical(row)).hexdigest()
                if actual != claimed:
                    return {"valid": False, "count": count, "error": "hash mismatch"}
                previous, count = claimed, count + 1
    except (OSError, ValueError, KeyError) as exc:
        return {"valid": False, "count": count, "error": str(exc)}
    return {"valid": True, "count": count, "head": previous}
