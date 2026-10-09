from __future__ import annotations
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
(root/"work").mkdir(exist_ok=True);(root/"work"/"answer.json").write_text(json.dumps(damage(oracle),sort_keys=True,separators=(",",":"))+"\n")
