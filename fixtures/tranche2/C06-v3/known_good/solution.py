def solve(db):
    out={'version':3,'users':[]}
    for row in db.get('users',[]):
        r=dict(row); r.setdefault('active',True); r.setdefault('display_name',r.get('name','')); r.pop('name',None); out['users'].append(r)
    return out
