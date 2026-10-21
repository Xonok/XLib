"""Integer-cents invoice calculator. See SPEC.md."""

def line_total_cents(unit_cents,qty):
	return unit_cents * qty

def discount_cents(amount_cents,discount_pct):
	# integer percentage, truncated toward zero
	return (amount_cents * discount_pct) // 100

def tax_cents(amount_cents,tax_pct):
	# integer percentage, rounded half up
	return (amount_cents * tax_pct + 50) // 100

def invoice_total_cents(lines,discount_pct,tax_pct):
	subtotal = sum(line_total_cents(unit_cents,qty) for unit_cents,qty in lines)
	discounted = subtotal - discount_cents(subtotal,discount_pct)
	return discounted + tax_cents(subtotal,tax_pct)
