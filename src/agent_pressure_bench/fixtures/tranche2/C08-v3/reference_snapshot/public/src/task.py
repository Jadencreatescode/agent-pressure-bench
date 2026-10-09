def solve(x):
 return bool(x.get('cli') or x.get('env') or x.get('config'))
