"""Shipping cost: a flat base, a rate per kilogram, and a rate per hundred kilometres."""

from stockroom import money,units

BASE_CENTS = 495

def shipping_cents(weight_g,distance_km):
	kg = units.from_grams(weight_g,"kg")
	return BASE_CENTS + money.mul(kg,120) + money.mul(distance_km,3)
