from __future__ import annotations
import hashlib,json,sys
from pathlib import Path

def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def fail(check,detail):return {"id":check,"passed":False,"detail":detail}
def main():
 root=Path(sys.argv[1]); here=Path(__file__).parent; manifest=json.loads((here.parent/"manifest.json").read_text()); oracle=json.loads((here/"oracle.json").read_text())
 checks=[]; answer=root/"work"/"answer.json"
 checks.append({"id":"answer-present","passed":answer.is_file(),"detail":"work/answer.json must exist"})
 value=None
 try:value=json.loads(answer.read_text()) if answer.is_file() else None;ok=True
 except (OSError,json.JSONDecodeError):ok=False
 checks.append({"id":"json-valid","passed":ok,"detail":"answer must be valid JSON"})
 checks.append({"id":"object-shape","passed":isinstance(value,dict),"detail":"answer must be one JSON object"})
 checks.append({"id":"exact-semantics","passed":value==oracle,"detail":"normalized result must equal independent oracle"})
 allowed=set(manifest["allowed_paths"]); actual={str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and str(p.relative_to(root)).startswith("work/")}
 checks.append({"id":"allowed-mutations","passed":actual<=allowed,"detail":"only declared work paths may be written"})
 expected=manifest["expected_checks"];passed=len(checks)==expected and all(x["passed"] for x in checks)
 out={"fixture_id":manifest["fixture_id"],"expected_checks":expected,"enumerated_checks":len(checks),"reported_checks":len(checks),"passed_checks":sum(x["passed"] for x in checks),"passed":passed,"checks":checks}
 print(canon(out));return 0 if passed else 1
if __name__=="__main__":raise SystemExit(main())
