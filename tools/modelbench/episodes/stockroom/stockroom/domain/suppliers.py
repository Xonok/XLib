"""Supplier terms and the amount owed to each."""

from stockroom import money

SUPPLIERS = {
	"nord": {"name":"Nord Parts","discount_pct":5},
	"alpine": {"name":"Alpine Fixings","discount_pct":2},
}

def payable_cents(cents,supplier):
	terms = SUPPLIERS[supplier]
	return cents - money.pct(cents,terms["discount_pct"])
