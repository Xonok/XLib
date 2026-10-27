"""A day's rota: shifts that must not overlap for the same worker.

Two shifts that merely touch — one ending at 12:00 and the next starting at 12:00 — do not
overlap. The conflict rule only fires when they share a minute.
"""

class Schedule:
	def __init__(self):
		self.shifts = []

	def overlaps(self,first,second):
		return (first.worker == second.worker
			and first.start < second.end and second.start < first.end)

	def conflicts(self,shift):
		return [other for other in self.shifts if self.overlaps(other,shift)]

	def add(self,shift):
		conflicts = self.conflicts(shift)
		if conflicts:
			raise ValueError(f"{shift.worker} is already on the rota at that time")
		self.shifts.append(shift)

	def total_minutes(self):
		return sum(shift.minutes() for shift in self.shifts)

	def by_worker(self,worker):
		return [shift for shift in self.shifts if shift.worker == worker]
