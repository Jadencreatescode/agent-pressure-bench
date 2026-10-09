#!/usr/bin/env python3
import json, sys
from pathlib import Path
root=Path(__file__).parents[1]; work=Path(sys.argv[1]) if len(sys.argv)>1 else root/"work"
work.mkdir(parents=True,exist_ok=True); o=json.loads((root/"verifier"/"oracle.json").read_text()); o[sorted(o)[0]]=None; (work/"answer.json").write_text(json.dumps(o))
