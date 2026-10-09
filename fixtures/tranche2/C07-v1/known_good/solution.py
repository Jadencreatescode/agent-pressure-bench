import csv, io
def solve(data):
    return list(csv.DictReader(io.StringIO(data)))
