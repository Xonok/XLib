from xlib_legacy import Config
# Pure Python port of Squirrel Eiserloh's SquirrelNoise5
def _squirrel_noise5(position: int, seed: int = 0) -> int:
	#Core 1D hash function
	SQ5_BIT_NOISE1 = 0xd2a80a3f
	SQ5_BIT_NOISE2 = 0xa884f197
	SQ5_BIT_NOISE3 = 0x6C736F4B
	SQ5_BIT_NOISE4 = 0xB79F3ABB
	SQ5_BIT_NOISE5 = 0x1b56c4f5

	mangled = position & 0xFFFFFFFF
	mangled = (mangled * SQ5_BIT_NOISE1) & 0xFFFFFFFF
	mangled = (mangled + seed) & 0xFFFFFFFF
	mangled = (mangled ^ (mangled >> 9)) & 0xFFFFFFFF
	mangled = (mangled + SQ5_BIT_NOISE2) & 0xFFFFFFFF
	mangled = (mangled ^ (mangled >> 11)) & 0xFFFFFFFF
	mangled = (mangled * SQ5_BIT_NOISE3) & 0xFFFFFFFF
	mangled = (mangled ^ (mangled >> 13)) & 0xFFFFFFFF
	mangled = (mangled + SQ5_BIT_NOISE4) & 0xFFFFFFFF
	mangled = (mangled ^ (mangled >> 15)) & 0xFFFFFFFF
	mangled = (mangled * SQ5_BIT_NOISE5) & 0xFFFFFFFF
	mangled = (mangled ^ (mangled >> 17)) & 0xFFFFFFFF
	return mangled

def get_1d_noise_uint(position: int, seed: int = 0) -> int:
	return _squirrel_noise5(position, seed)
def get_1d_noise_zero_to_one(position: int, seed: int = 0) -> float:
	return _squirrel_noise5(position, seed) / 0xFFFFFFFF
def get_1d_noise_neg_one_to_one(position: int, seed: int = 0) -> float:
	return (int(_squirrel_noise5(position, seed)) & 0x7FFFFFFF) / 0x7FFFFFFF - 0.5

def get_2d_noise_uint(x: int, y: int, seed: int = 0) -> int:
	PRIME = 198491317
	return _squirrel_noise5(x + (PRIME * y), seed)
def get_2d_noise_zero_to_one(x: int, y: int, seed: int = 0) -> float:
	return get_2d_noise_uint(x, y, seed) / 0xFFFFFFFF
def get_2d_noise_neg_one_to_one(x: int, y: int, seed: int = 0) -> float:
	return (get_2d_noise_uint(x, y, seed) & 0x7FFFFFFF) / 0x7FFFFFFF - 0.5

def get_3d_noise_uint(x: int, y: int, z: int, seed: int = 0) -> int:
	PRIME1 = 198491317
	PRIME2 = 6542989
	return _squirrel_noise5(x + (PRIME1 * y) + (PRIME2 * z), seed)
def get_3d_noise_zero_to_one(x: int, y: int, z: int, seed: int = 0) -> float:
	return get_3d_noise_uint(x, y, z, seed) / 0xFFFFFFFF
def get_3d_noise_neg_one_to_one(x: int, y: int, z: int, seed: int = 0) -> float:
	return (get_3d_noise_uint(x, y, z, seed) & 0x7FFFFFFF) / 0x7FFFFFFF - 0.5

def get_4d_noise_uint(x: int, y: int, z: int, t: int, seed: int = 0) -> int:
	PRIME1 = 198491317
	PRIME2 = 6542989
	PRIME3 = 357239
	return _squirrel_noise5(x + (PRIME1 * y) + (PRIME2 * z) + (PRIME3 * t), seed)
def get_4d_noise_zero_to_one(x: int, y: int, z: int, t: int, seed: int = 0) -> float:
	return get_4d_noise_uint(x, y, z, t, seed) / 0xFFFFFFFF
def get_4d_noise_neg_one_to_one(x: int, y: int, z: int, t: int, seed: int = 0) -> float:
	return (get_4d_noise_uint(x, y, z, t, seed) & 0x7FFFFFFF) / 0x7FFFFFFF - 0.5
