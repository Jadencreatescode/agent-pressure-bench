def solve(p):
    if not isinstance(p,str) or not p.startswith('/'): raise ValueError('absolute path required')
    out=[]
    for part in p.split('/'):
        if part in ('','.'): continue
        if part=='..':
            if not out: raise ValueError('traversal')
            out.pop()
        else: out.append(part)
    return '/'+ '/'.join(out)
