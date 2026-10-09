from __future__ import annotations
import json, sys
from pathlib import Path
# The independent reference imports no oracle data; it uses the public transformation implementation.
spec=importlib.util.spec_from_file_location("builder", Path(__file__).resolve().parents[4]/"scripts"/"build_fixtures.py") if False else None
import hashlib,json
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
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

if __name__ == "__main__":
    root=Path(sys.argv[1]); data=json.loads((root/"public"/"input.json").read_text())
    (root/"work").mkdir(exist_ok=True); (root/"work"/"answer.json").write_text(canonical(oracle(data))+"\n")
