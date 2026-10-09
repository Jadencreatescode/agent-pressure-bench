#!/usr/bin/env python3
import copy, importlib.util, json, sys
from pathlib import Path
candidate, cases_path = map(Path, sys.argv[1:3])
try:
    spec=importlib.util.spec_from_file_location("candidate_solution",candidate)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    cases=json.loads(cases_path.read_text()); original=copy.deepcopy(cases)
    got=[mod.solve(copy.deepcopy(c["input"])) for c in cases]
    expected=[c["expected"] for c in cases]
    report={"semantics":got==expected,"input_purity":cases==original}
except Exception as exc:
    report={"semantics":False,"input_purity":False,"error":type(exc).__name__}
print(json.dumps(report,sort_keys=True))
sys.exit(0 if report["semantics"] and report["input_purity"] else 1)
