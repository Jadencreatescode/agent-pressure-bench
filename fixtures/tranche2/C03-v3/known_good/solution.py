def solve(statuses):
    delays=[]
    for i,s in enumerate(statuses[:4]):
        if s=='ok': return {'result':'ok','delays':delays,'attempts':i+1}
        if s!='retry': return {'result':'error','delays':delays,'attempts':i+1}
        if i<3: delays.append(min(2**i,4))
    return {'result':'exhausted','delays':delays,'attempts':min(len(statuses),4)}
