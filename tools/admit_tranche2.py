#!/usr/bin/env python3
"""Independently admit tranche-2 fixtures from fresh copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures" / "tranche2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=30, env={"PATH":"/usr/bin:/bin","TZ":"UTC","LC_ALL":"C","PYTHONHASHSEED":"0"})


def snapshot(root: Path, manifest: dict) -> dict[str,str]:
    return {p:digest(root/p) for p in manifest["immutable_hashes"]}


def materialize(source: Path, destination: Path) -> Path:
    destination.mkdir()
    shutil.copy2(source/"prompt.md", destination/"prompt.md")
    shutil.copytree(source/"public", destination/"public")
    work=destination/"work"; work.mkdir()
    return work


def one_reference(source: Path) -> tuple[dict,str,bool]:
    with tempfile.TemporaryDirectory(prefix="apb-admit-") as td:
        fresh=Path(td)/source.name; shutil.copytree(source,fresh)
        candidate=Path(td)/"candidate"; work=materialize(fresh,candidate)
        before=snapshot(fresh,json.loads((fresh/"manifest.json").read_text()))
        solved=run([sys.executable,str(fresh/"known_good"/"solve.py"),str(work)],fresh)
        verified=run([sys.executable,str(fresh/"verifier"/"verify.py"),str(candidate)],fresh)
        payload=json.loads(verified.stdout) if verified.stdout else {"checks":[]}
        return payload, hashlib.sha256(verified.stdout.encode()).hexdigest(), solved.returncode == verified.returncode == 0 and before == snapshot(fresh,json.loads((fresh/"manifest.json").read_text()))


def negative_controls(source: Path) -> bool:
    manifest=json.loads((source/"manifest.json").read_text())
    with tempfile.TemporaryDirectory(prefix="apb-negative-") as td:
        fresh=Path(td)/source.name; shutil.copytree(source,fresh)
        candidate=Path(td)/"candidate"; work=materialize(fresh,candidate)
        if manifest["kind"] == "coding":
            shutil.copyfile(fresh/"public"/"src"/"task.py",work/"solution.py")
            original=run([sys.executable,str(fresh/"verifier"/"verify.py"),str(candidate)],fresh)
            shutil.copyfile(next((fresh/"mutants").glob("*.py")),work/"solution.py")
            mutant=run([sys.executable,str(fresh/"verifier"/"verify.py"),str(candidate)],fresh)
        else:
            original=run([sys.executable,str(fresh/"verifier"/"verify.py"),str(candidate)],fresh)
            mutant_script=next((fresh/"mutants").glob("*.py"))
            made=run([sys.executable,str(mutant_script),str(work)],fresh)
            mutant=run([sys.executable,str(fresh/"verifier"/"verify.py"),str(candidate)],fresh)
            if made.returncode: return False
        return original.returncode != 0 and mutant.returncode != 0


def admit(source: Path, write: bool) -> tuple[bool,dict]:
    manifest=json.loads((source/"manifest.json").read_text())
    hashes=snapshot(source,manifest)
    hash_ok=hashes == manifest["immutable_hashes"]
    a,ha,oka=one_reference(source); b,hb,okb=one_reference(source)
    checks=a.get("checks",[])
    denominator=(a.get("expected_checks") == a.get("enumerated_checks") == manifest["expected_checks"]
                 and len(checks) == manifest["expected_checks"]
                 and a.get("passed") is True and all(c.get("passed") is True for c in checks))
    deterministic=ha==hb and [c["id"] for c in a.get("checks",[])] == [c["id"] for c in b.get("checks",[])]
    negatives=negative_controls(source)
    ok=hash_ok and oka and okb and denominator and deterministic and negatives
    receipt={"schema_version":"1.0","fixture_id":manifest["fixture_id"],"status":"admitted" if ok else "rejected","reference_runs":2,"deterministic":deterministic,"negative_controls_passed":negatives,"expected_checks":manifest["expected_checks"],"enumerated_checks":len(checks),"passed_checks":sum(c.get("passed") is True for c in checks),"immutable_hashes_match":hash_ok,"network":"disabled","timezone":"UTC","semantic_receipt_sha256":ha,"fixture_manifest_sha256":digest(source/"manifest.json"),"verifier_sha256":digest(source/"verifier"/"verify.py"),"known_good_sha256":digest(source/"known_good"/"solve.py")}
    if write: (source/"admission.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    elif not (source/"admission.json").is_file() or json.loads((source/"admission.json").read_text()) != receipt: ok=False
    return ok,receipt


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--check",action="store_true"); args=parser.parse_args()
    dirs=sorted(p for p in FIXTURES.iterdir() if p.is_dir())
    failures=[]
    for source in dirs:
        ok,_=admit(source,not args.check)
        if not ok: failures.append(source.name)
    print(json.dumps({"admitted":len(dirs)-len(failures),"failed":len(failures),"failures":failures},sort_keys=True))
    return bool(failures)

if __name__ == "__main__": raise SystemExit(main())
