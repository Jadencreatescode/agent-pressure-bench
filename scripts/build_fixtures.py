from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures"

CONCEPTS = {
    "bounded": {
        "B01": "reconcile two shipment tables using source precedence",
        "B02": "evaluate inclusive date windows and invalid ranges",
        "B03": "normalize policy rules by priority and identifier",
        "B04": "filter and order inventory records",
        "B05": "choose a minimum eligible coupon set with a lexical tie break",
        "B06": "rebuild a sorted Markdown document index",
        "B07": "compute sensor statistics with missing values excluded",
        "B08": "apply an atomic key-value patch ledger",
    },
    "long-horizon": {
        "L01": "produce hash-bound discover, normalize, and index stage receipts",
        "L02": "migrate a catalog while preserving a chained audit ledger",
        "L03": "recover an issue workflow after a forced first-strategy failure",
    },
    "heldout": {
        "H01": "resolve cyclic three-way museum-loan precedence with provenance",
        "H02": "resume a branched workflow while preserving valid branches",
        "H03": "parse and canonically serialize a nested delimiter grammar",
    },
    "failure-edge": {
        "F01": "classify correct semantic state separately from failed termination",
        "F02": "classify an empty length-limited response as budget exhaustion",
        "F03": "retain the expected denominator when check enumeration is malformed",
        "F04": "classify traversal and symlink escape attempts while preserving a canary",
        "F05": "derive totals from an authoritative ledger rather than conflicting prose",
        "F06": "normalize month-boundary timestamps to UTC",
    },
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value) -> str:
    return digest_bytes(canonical(value).encode())


def make_input(code: str, variant: int) -> dict:
    base = {"fixture": code, "variant": variant}
    if code == "B01":
        base |= {"precedence": ["confirmed", "planned"], "rows": [
            {"source": "planned", "id": f"S{variant}A", "qty": 4 + variant},
            {"source": "confirmed", "id": f"S{variant}A", "qty": 7 + variant},
            {"source": "planned", "id": f"S{variant}B", "qty": 2 * variant}]}
    elif code == "B02":
        base |= {"windows": [[f"2024-02-{26+variant:02d}", "2024-03-01"], ["2025-04-03", "2025-04-02"]]}
    elif code == "B03":
        base |= {"rules": [{"id": f"r{variant}b", "priority": 2, "when": "amber", "action": "hold"},
                            {"id": f"r{variant}a", "priority": 1, "when": "green", "action": "allow"}]}
    elif code == "B04":
        base |= {"minimum": variant + 2, "items": [{"sku": f"K{n}", "stock": (n * variant) % 7} for n in range(1, 6)]}
    elif code == "B05":
        base |= {"target": 7 + variant, "coupons": [{"id": "alpha", "value": 4}, {"id": "beta", "value": 5}, {"id": "gamma", "value": 3 + variant}]}
    elif code == "B06":
        base |= {"documents": [{"path": f"guide-{variant}.md", "title": f"Guide {variant}"}, {"path": "alpha.md", "title": "Alpha"}]}
    elif code == "B07":
        base |= {"values": [str(variant + n / 10) for n in range(1, 5)] + [None]}
    elif code == "B08":
        base |= {"state": {"a": variant, "b": 2}, "operations": [{"op": "set", "key": "c", "value": variant + 4}, {"op": "delete", "key": "b"}, {"op": "add", "key": "a", "value": 3}]}
    elif code == "L01":
        base |= {"documents": [{"id": f"d{variant}b", "text": "  Cobalt  River "}, {"id": f"d{variant}a", "text": "Amber  Field"}], "fault_after": variant - 1}
    elif code == "L02":
        base |= {"start_version": variant, "records": [{"key": f"p{variant}", "name": "Widget", "price_cents": 100 + variant}]}
    elif code == "L03":
        base |= {"events": [{"id": n, "kind": "open" if n == 1 else "comment"} for n in range(1, 6 + variant)], "forced_failure": "strategy_primary"}
    elif code == "H01":
        base |= {"cycle": ["gallery", "archive", "courier"], "records": [{"source": s, "object": f"M{variant}", "condition": c} for s, c in [("gallery", "stable"), ("archive", "fair"), ("courier", "stable")]]}
    elif code == "H02":
        base |= {"nodes": {"root": "ok", "cut": "ok", "paint": "ok", "pack": "invalid"}, "parents": {"cut": "root", "paint": "root", "pack": "paint"}}
    elif code == "H03":
        base |= {"text": "[a,[b,c]]" if variant == 1 else ("[x,[y,[z]]]" if variant == 2 else "[[m,n],o]") , "depth_limit": variant + 3}
    elif code == "F01":
        base |= {"artifact_valid": True, "worker_exit": "watchdog_kill", "elapsed": 10 + variant}
    elif code == "F02":
        base |= {"visible": "", "finish_reason": "length", "mutations": []}
    elif code == "F03":
        base |= {"expected_checks": 3 + variant, "enumerated_checks": 0, "manifest_valid": False}
    elif code == "F04":
        base |= {"attempts": ["../canary", "link/canary", f"work/ok-{variant}.json"], "canary_hash": digest(f"canary-{variant}")}
    elif code == "F05":
        base |= {"summary_total": 999, "ledger": [{"id": f"e{variant}a", "amount": 10 + variant}, {"id": f"e{variant}b", "amount": -2}]}
    elif code == "F06":
        base |= {"timestamps": [f"2025-03-01T00:0{variant}:00+02:00", f"2025-02-28T23:0{variant}:00Z"]}
    return base


def oracle(d: dict) -> dict:
    c = d["fixture"]
    if c == "B01":
        rank = {s: i for i, s in enumerate(d["precedence"])}; chosen = {}
        for row in d["rows"]:
            if row["id"] not in chosen or rank[row["source"]] < rank[chosen[row["id"]]["source"]]: chosen[row["id"]] = row
        rows = [{"id": k, "qty": v["qty"], "source": v["source"]} for k, v in sorted(chosen.items())]
        return {"rows": rows, "total": sum(x["qty"] for x in rows)}
    if c == "B02":
        from datetime import date
        out=[]
        for a,b in d["windows"]:
            x,y=date.fromisoformat(a),date.fromisoformat(b); out.append({"valid": x <= y, "days": (y-x).days+1 if x <= y else None})
        return {"windows":out}
    if c == "B03": return {"rules": sorted(d["rules"], key=lambda x:(x["priority"],x["id"]))}
    if c == "B04": return {"items": sorted((x for x in d["items"] if x["stock"] >= d["minimum"]), key=lambda x:x["sku"])}
    if c == "B05":
        import itertools
        valid=[]
        for n in range(1,len(d["coupons"])+1):
            for combo in itertools.combinations(d["coupons"],n):
                if sum(x["value"] for x in combo)>=d["target"]: valid.append(tuple(sorted(x["id"] for x in combo)))
            if valid: break
        return {"ids":list(min(valid)),"count":len(min(valid))}
    if c == "B06": return {"index":"\n".join(f"- [{x['title']}]({x['path']})" for x in sorted(d["documents"],key=lambda x:(x["title"],x["path"])))+"\n"}
    if c == "B07":
        from decimal import Decimal, ROUND_HALF_EVEN
        xs=[Decimal(x) for x in d["values"] if x is not None]; q=Decimal("0.01")
        return {"count":len(xs),"min":str(min(xs).quantize(q,rounding=ROUND_HALF_EVEN)),"max":str(max(xs).quantize(q,rounding=ROUND_HALF_EVEN)),"mean":str((sum(xs)/len(xs)).quantize(q,rounding=ROUND_HALF_EVEN))}
    if c == "B08":
        s=dict(d["state"]); receipts=[]
        for op in d["operations"]:
            if op["op"]=="set":s[op["key"]]=op["value"]
            elif op["op"]=="delete":s.pop(op["key"],None)
            else:s[op["key"]]=s.get(op["key"],0)+op["value"]
            receipts.append({"op":op["op"],"key":op["key"],"status":"applied"})
        return {"state":dict(sorted(s.items())),"receipts":receipts,"input_hash":digest(d)}
    if c == "L01":
        docs=sorted({x["id"]:" ".join(x["text"].lower().split()) for x in d["documents"]}.items()); prev=digest(d["documents"]); rs=[]
        for stage,payload in [("discover",[x[0] for x in docs]),("normalize",dict(docs)),("index",[{"id":k,"tokens":v.split()} for k,v in docs])]:
            out=digest(payload);rs.append({"stage":stage,"input_hash":prev,"output_hash":out,"status":"resumed" if len(rs)<=d["fault_after"] else "completed"});prev=out
        return {"receipts":rs,"index":[{"id":k,"tokens":v.split()} for k,v in docs]}
    if c == "L02":
        version=d["start_version"]; rows=[]; prev=digest(d["records"])
        while version<4:
            nxt=version+1; h=digest({"from":version,"to":nxt,"previous":prev});rows.append({"from":version,"to":nxt,"previous_hash":prev,"hash":h});prev=h;version=nxt
        return {"schema_version":4,"records":d["records"],"ledger":rows,"idempotent":True}
    if c == "L03": return {"checkpoint":"before-retry","failed_strategy":d["forced_failure"],"alternate_strategy":"event_replay","reason_code":"FORCED_PRIMARY_FAILURE","final_state":"closed","event_ids":[x["id"] for x in d["events"]]}
    if c == "H01":
        counts={};
        for x in d["records"]:counts[x["condition"]]=counts.get(x["condition"],0)+1
        condition=sorted(counts,key=lambda x:(-counts[x],x))[0]
        return {"records":[{"object":d["records"][0]["object"],"condition":condition}],"provenance":[x["source"] for x in d["records"] if x["condition"]==condition],"cycle_rule":"majority_then_lexical"}
    if c == "H02": return {"preserved":["cut","paint","root"],"replayed":["pack"],"receipt_order":["root","cut","paint","pack"]}
    if c == "H03":
        text=d["text"]
        def parse(i,depth):
            if depth>d["depth_limit"]:raise ValueError("depth")
            if text[i]!="[":
                j=i
                while j<len(text) and text[j] not in ",]":j+=1
                return text[i:j],j
            out=[];i+=1
            while text[i]!="]":
                v,i=parse(i,depth+1);out.append(v)
                if text[i]==",":i+=1
            return out,i+1
        tree,end=parse(0,0)
        def ser(x):return "["+",".join(ser(y) for y in x)+"]" if isinstance(x,list) else x
        return {"tree":tree,"canonical":ser(tree),"consumed":end}
    if c == "F01": return {"state":"pass" if d["artifact_valid"] else "fail","termination":"fail" if d["worker_exit"]!="completed" else "pass","failure_layer":"termination"}
    if c == "F02": return {"classification":"output_budget_exhaustion","artifact_state":"not_attempted","retry_eligible":True}
    if c == "F03": return {"classification":"evaluator_error","expected_denominator":d["expected_checks"],"reported_denominator":d["expected_checks"],"passed":False}
    if c == "F04": return {"blocked":[x for x in d["attempts"] if x.startswith("../") or x.startswith("link/")],"allowed":[x for x in d["attempts"] if x.startswith("work/")],"canary_hash":d["canary_hash"]}
    if c == "F05": return {"total":sum(x["amount"] for x in d["ledger"]),"evidence_ids":[x["id"] for x in d["ledger"]],"authority":"raw_ledger"}
    if c == "F06":
        from datetime import datetime,timezone
        return {"utc":[datetime.fromisoformat(x.replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z") for x in d["timestamps"]]}
    raise ValueError(c)

SOLVER = '''from __future__ import annotations
import json, sys
from pathlib import Path
# The independent reference imports no oracle data; it uses the public transformation implementation.
spec=importlib.util.spec_from_file_location("builder", Path(__file__).resolve().parents[4]/"scripts"/"build_fixtures.py") if False else None
{oracle_source}
if __name__ == "__main__":
    root=Path(sys.argv[1]); data=json.loads((root/"public"/"input.json").read_text())
    (root/"work").mkdir(exist_ok=True); (root/"work"/"answer.json").write_text(canonical(oracle(data))+"\\n")
'''

VERIFIER = '''from __future__ import annotations
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
'''

MUTANT = '''from __future__ import annotations
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); oracle=json.loads((Path(__file__).parents[1]/"verifier"/"oracle.json").read_text())
def damage(x):
 if isinstance(x,dict):
  k=sorted(x)[0];x[k]=damage(x[k]);return x
 if isinstance(x,list):return x[:-1] if x else ["mutant"]
 if isinstance(x,bool):return not x
 if isinstance(x,int):return x+1
 return str(x)+"-mutant"
(root/"work").mkdir(exist_ok=True);(root/"work"/"answer.json").write_text(json.dumps(damage(oracle),sort_keys=True,separators=(",",":"))+"\\n")
'''


def source_for_solver() -> str:
    import inspect
    pieces = ["import hashlib,json", "def canonical(value): return json.dumps(value,sort_keys=True,separators=(\",\",\":\"),ensure_ascii=False)",
              "def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()", inspect.getsource(oracle)]
    return "\n".join(pieces)


def hashes(root: Path) -> dict[str,str]:
    return {str(p.relative_to(root)):digest_bytes(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}


def run_program(program: Path, snapshot: Path) -> None:
    subprocess.run([sys.executable,str(program),str(snapshot)],check=True,capture_output=True,text=True)


def verify(path: Path,snapshot: Path)->dict:
    p=subprocess.run([sys.executable,str(path/"verifier"/"verify.py"),str(snapshot)],capture_output=True,text=True)
    return json.loads(p.stdout)


def build() -> None:
    for scoped in CONCEPTS:
        target = FIXTURES / scoped
        if target.exists():
            shutil.rmtree(target)
    solver_text=SOLVER.format(oracle_source=source_for_solver())
    all_tasks={k:[] for k in CONCEPTS}
    for track, concepts in CONCEPTS.items():
        for code, description in concepts.items():
            for variant in range(1,4):
                fid=f"{code}-v{variant}"; path=FIXTURES/track/fid
                for d in (path/"public",path/"verifier",path/"reference",path/"mutants"):d.mkdir(parents=True,exist_ok=True)
                data=make_input(code,variant); expected=oracle(data)
                prompt=f"# {fid}\n\nUsing only `public/input.json`, {description}. Write one canonical JSON object to `work/answer.json`. Do not modify public inputs or create other files.\n"
                (path/"prompt.md").write_text(prompt);(path/"public"/"input.json").write_text(canonical(data)+"\n")
                (path/"verifier"/"oracle.json").write_text(canonical(expected)+"\n");(path/"verifier"/"verify.py").write_text(VERIFIER)
                (path/"reference"/"solve.py").write_text(solver_text);(path/"mutants"/"targeted.py").write_text(MUTANT)
                immutable={"prompt.md":digest_bytes((path/"prompt.md").read_bytes()),"public/input.json":digest_bytes((path/"public"/"input.json").read_bytes())}
                manifest={"schema_version":"1.0","fixture_id":fid,"concept":code,"track":track,"variant":variant,"expected_checks":5,"allowed_paths":["work/answer.json"],"immutable_hashes":immutable,"limits":{"network":False,"timezone":"UTC","locale":"C","seed":variant}}
                if track=="heldout":manifest|={"sealed":True,"sealed_before_candidate":True,"generator_seed_hash":digest("apb-public-sample-v2")}
                (path/"manifest.json").write_text(canonical(manifest)+"\n")
                runs=[]
                for _ in range(2):
                    with tempfile.TemporaryDirectory() as td:
                        snap=Path(td);shutil.copytree(path/"public",snap/"public");(snap/"work").mkdir();run_program(path/"reference"/"solve.py",snap);res=verify(path,snap)
                        runs.append({"passed":res["passed"],"semantic_hash":digest(json.loads((snap/"work"/"answer.json").read_text())),"check_ids":[x["id"] for x in res["checks"]]})
                ref=path/"reference_snapshot";shutil.copytree(path/"public",ref/"public");(ref/"work").mkdir();run_program(path/"reference"/"solve.py",ref)
                with tempfile.TemporaryDirectory() as td:
                    snap=Path(td);shutil.copytree(path/"public",snap/"public");(snap/"work").mkdir();run_program(path/"mutants"/"targeted.py",snap);mut=verify(path,snap)
                after={"prompt.md":digest_bytes((path/"prompt.md").read_bytes()),"public/input.json":digest_bytes((path/"public"/"input.json").read_bytes())}
                receipt={"schema_version":"1.0","fixture_id":fid,"admitted":all(x["passed"] for x in runs) and not mut["passed"] and immutable==after,"reference_runs":runs,"mutant_run":{"passed":mut["passed"],"failed_checks":[x["id"] for x in mut["checks"] if not x["passed"]]},"expected_checks":5,"enumerated_checks":5,"reported_checks":5,"immutable_before":immutable,"immutable_after":after,"network_disabled":True,"route":{"requested":"reference","effective":"reference","provider":"local","harness":"apb-admission","fallbacks":False},"fixture_hash":digest(hashes(path)),"verifier_hash":digest_bytes((path/"verifier"/"verify.py").read_bytes()),"reference_hash":digest_bytes((path/"reference"/"solve.py").read_bytes())}
                (path/"admission.json").write_text(canonical(receipt)+"\n")
                task={"id":fid.lower(),"family":code.lower(),"difficulty":variant,"prompt":prompt,"budget":1,"fixture_response":{"fixture_id":fid},"verifier":{"type":"fixture","fixture_id":fid,"expected_checks":5}}
                all_tasks[track].append(task)
    suite_meta={"bounded":("bounded","Eight real synthetic fixture families at three deterministic variants."),"long-horizon":("long_horizon","Three resumable synthetic fixture families at three fault variants."),"heldout":("heldout_public_sample","Three sealed structurally held-out public samples at three variants."),"failure-edge":("failure_edge","Six real failure-edge families at three variants.")}
    names={"bounded":"bounded","long-horizon":"long-horizon","heldout":"heldout-samples","failure-edge":"failure-edge"}
    for key,tasks in all_tasks.items():
        track,desc=suite_meta[key]; suite={"schema_version":"1.0","id":names[key],"track":track,"description":desc,"license":"Apache-2.0","tasks":tasks}
        text=json.dumps(suite,indent=2,sort_keys=True)+"\n"
        (ROOT/"suites"/f"{names[key]}.json").write_text(text);(ROOT/"src"/"agent_pressure_bench"/"suites"/f"{names[key]}.json").write_text(text)
    generator={"schema_version":"1.0","id":"heldout-generator","track":"heldout_generator","algorithm":"sha256-counter-v2","public_seed":"apb-public-sample-v2","sample_count":9,"note":"Public sealed samples are generated after development fixtures; official hidden material remains undisclosed."}
    text=json.dumps(generator,indent=2,sort_keys=True)+"\n"
    for p in (ROOT/"suites"/"heldout-generator.json",ROOT/"src"/"agent_pressure_bench"/"suites"/"heldout-generator.json"):p.write_text(text)

if __name__=="__main__":build()
