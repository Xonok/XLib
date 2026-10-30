def parse_config(text):
    lines = text.splitlines()
    return {k: v for k, v in (l.split('=', 1) for l in lines if '=' in l)}
