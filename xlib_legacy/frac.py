from xlib_legacy import squirrelhash
#Alpha refers to mandelbrot's concept of wild randomness.
#Currently not needed, since 1/roll already does that.
#Scale is just a multiplier on output. Optional.
def rand(seed,idx,alpha=1,scale=1):
	roll = squirrelhash.get_1d_noise_zero_to_one(idx,seed)
	return ((1/roll)**alpha)*scale
def rand_2d(seed,x,y,alpha=1,scale=1):
	roll = squirrelhash.get_2d_noise_zero_to_one(x,y,seed)
	return ((1/roll)**alpha)*scale
for i in range(10):
	print(rand(127,i))
for i in range(3):
	for j in range(4):
		print(rand_2d(127,i,j))