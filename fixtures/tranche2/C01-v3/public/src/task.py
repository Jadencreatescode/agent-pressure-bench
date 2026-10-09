def solve(p):
 return '/'.join(x for x in p.split('/') if x not in ('','.','..'))
