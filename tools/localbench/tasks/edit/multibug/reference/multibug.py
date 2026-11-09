def average(nums):
    if not nums:
        return 0
    return sum(nums) / len(nums)

def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def dedup(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
