import json
def solve(lines):
    good=[]
    for line in lines:
        try: good.append(json.loads(line))
        except (ValueError,TypeError): break
    return good
