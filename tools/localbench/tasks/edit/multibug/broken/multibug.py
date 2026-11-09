def average(nums):
    if not nums:
        return 0
    return sum(nums) / (len(nums) + 1)

def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x >= hi:
        return hi
    return x

def dedup(items):
    return list(set(items))
