import json
def solve(lines):
 out=[]
 for x in lines:
  try: out.append(json.loads(x))
  except ValueError: continue
 return out
