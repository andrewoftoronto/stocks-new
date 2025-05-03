from decimal import Decimal
from serialize_context import SerializeContext
from copy import deepcopy


def currency_collection_to_string(dict) -> str:
	text = "{"
	
	items = list(dict.items())
	for (i, (key, value)) in enumerate(items):
		text += f"{key}: {value:.2f}"
		if i < len(items) - 1:
			text += ", "
	text += "}"
	return text


def combine_currency_collections(a, b):
	c = deepcopy(a)
	for (currency, amount) in b.items():
		if currency in c:
			c[currency] += amount
		else:
			c[currency] = amount
	return c


def currency_collection_get(collection, currency_kind):
	if currency_kind in collection:
		return collection[currency_kind]
	else:
		return Decimal(0)


def add_to_currency_collection(collection, amount, currency_kind):
	if currency_kind in collection:
		collection[currency_kind] += amount
	else:
		collection[currency_kind] = amount


def get_currency_from_collection(collection, currency_kind) -> Decimal:
	if currency_kind not in collection:
		return Decimal(0)
	else:
		return collection[currency_kind]

def decimal_get(dic, key, default_value):
	''' Get the value for the given key in the dictionary, casting to Decimal
	    if it is not null. '''

	value = dic.get(key, default_value)
	if value is not None:
		return Decimal(value)
	else:
		return value
	

def to_dict(x, context: SerializeContext):
    ''' Correctly applies to_dict() to things that might be nested in lists. '''

    if isinstance(x, list):
        return [to_dict(i, context) for i in x]
    else:
        return x.to_dict(context)


def penny_round(x, fn=round):
	if isinstance(x, tuple):
		new_list = []
		for item in x:
			new_list.append(penny_round(item))
		return new_list
	elif isinstance(x, list):
		new_list = []
		for item in x:
			new_list.append(penny_round(item))
		return new_list
	elif isinstance(x, int):
		return x
	else:
		y = fn(x * 100) / 100
		if isinstance(x, Decimal):
			y = Decimal(y)
		return y