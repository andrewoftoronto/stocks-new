from currency import Currency, currency_from_common
from currencies import Currencies


class UnsetArg:
    pass


def list_from_dict(data_dict, key, read_fn):
    if data_dict is None:
        return []
    else:
        raw_list_data = data_dict[key]
        return [read_fn(e) for e in raw_list_data]
    

def read_from_dict(key, data_dict, default_value=UnsetArg()):
    if data_dict is None:
        if isinstance(default_value, UnsetArg):
            raise Exception("No default value given and data_dict is None")

        return default_value
    else:
        return data_dict[key]


def read_from_partial_dict(key, data_dict, default_value=UnsetArg()):
    if data_dict is None or key not in data_dict:
        if isinstance(default_value, UnsetArg):
            raise Exception("No default value given and data_dict is None")

        return default_value
    else:
        return data_dict[key]


def fixup_price(price, currency_kind):
    if isinstance(price, Currency):
        return price
    else:
        return currency_from_common(price, currency_kind)


def fixup_currencies(price, currency_kind):
    if isinstance(price, Currencies):
        return price
    
    currency = fixup_price(price)
    return Currencies([currency])