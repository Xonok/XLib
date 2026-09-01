from db import model

def create_conn():
	return model.Connection()

def describe():
	return type(model.Connection()).__name__
