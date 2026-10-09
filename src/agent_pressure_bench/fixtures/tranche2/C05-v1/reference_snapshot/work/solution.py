def solve(g):
    nodes=sorted(set(g)|{x for vs in g.values() for x in vs}); indeg={n:0 for n in nodes}; out={n:[] for n in nodes}
    for n,deps in g.items():
        for d in deps: out[d].append(n); indeg[n]+=1
    ready=sorted(n for n in nodes if indeg[n]==0); order=[]
    while ready:
        n=ready.pop(0); order.append(n)
        for q in sorted(out[n]):
            indeg[q]-=1
            if indeg[q]==0: ready.append(q); ready.sort()
    return order if len(order)==len(nodes) else {'cycle':sorted(n for n in nodes if indeg[n])}
