def solve(x):
  vals=[x.get('cli'),x.get('env'),x.get('config'),False]
  v=next(v for v in vals if v is not None)
  if type(v) is not bool: raise ValueError('flag must be boolean')
  return v
