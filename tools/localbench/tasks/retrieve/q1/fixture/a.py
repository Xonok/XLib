def load_data(path):
    with open(path) as f:
        return f.read()

def normalize_path(p):
    return p.replace('\\', '/')
