import csv

def total(path):
    with open(path) as f:
        reader = csv.reader(f)
        return sum(int(row[0]) for row in reader)
