import csv

def total(path):
    with open(path) as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(int(row[0]) for row in reader)
