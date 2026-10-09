def solve(db):
 return {'version':3,'users':[dict(x,active=True) for x in db.get('users',[])]}
