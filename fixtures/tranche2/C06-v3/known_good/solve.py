#!/usr/bin/env python3
import shutil, sys
from pathlib import Path
root=Path(__file__).parents[1]; work=Path(sys.argv[1]) if len(sys.argv)>1 else root/"work"
work.mkdir(parents=True,exist_ok=True); shutil.copyfile(root/"known_good"/"solution.py",work/"solution.py")
