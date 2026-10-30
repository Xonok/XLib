from a import normalize_path

def save(item, dest):
    dest = normalize_path(dest)
    with open(dest, 'w') as f:
        f.write(item)
