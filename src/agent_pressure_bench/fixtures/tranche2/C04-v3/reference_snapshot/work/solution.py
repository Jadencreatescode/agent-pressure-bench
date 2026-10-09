import unicodedata
def solve(s):
    s=unicodedata.normalize('NFC',s); n=0; joined=False
    for ch in s:
        if unicodedata.combining(ch): continue
        if ch=='\u200d': joined=True; continue
        if joined: joined=False; continue
        n+=1
    return n
