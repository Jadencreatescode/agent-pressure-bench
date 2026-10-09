import unicodedata
def solve(s):
 return sum(not unicodedata.combining(c) for c in s)
