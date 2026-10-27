"""A shift on the rota.

Times are minutes since midnight, and a shift always ends later the same day: the rota
does not model shifts that cross midnight.
"""

class Shift:
	def __init__(self,worker,start,end):
		if end <= start:
			raise ValueError("a shift ends later the same day")
		self.worker,self.start,self.end = worker,start,end

	def minutes(self):
		return self.end - self.start

	def hours_text(self):
		hours,minutes = divmod(self.minutes(),60)
		return f"{hours}h{minutes:02d}"
