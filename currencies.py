from currency import Currency
from copy import copy


class Currencies:
    def __init__(self, data=None):
        if data is None:
            self.data = {}
        elif isinstance(data, list):
            self.data = {c.unit_kind:c for c in data}
        elif isinstance(data, Currency):
            self.data = {data.unit_kind:data}
        else:
            self.data = data

    def has_negative(self):
        for k, v in self.data.items():
            if v < 0:
                return True
        return False

    def __repr__(self):
        if len(self.data) == 0:
            return "0C"

        s = ""
        for k, v in self.data.items():
            s += f"{v} "
        return s

    def __add__(self, other):
        new_data = {}
        for k, my_currency in self.data.items():
            new_data[k] = copy(my_currency)

        if isinstance(other, Currencies):    
            for k, other_currency in other.data.items():
                if k in new_data:
                    new_data[k] = new_data[k] + other_currency
                else:
                    new_data[k] = copy(other_currency)
        elif isinstance(other, Currency):
            if other.unit_kind in new_data:
                new_data[other.unit_kind] = new_data[other.unit_kind] + other
            else:
                new_data[other.unit_kind] = copy(other)
        else:
            raise Exception(f"invalid other type to add: {other}")
        return Currencies(new_data)

    def __sub__(self, other):
        new_data = {}
        for k, my_currency in self.data.items():
            new_data[k] = copy(my_currency)

        if isinstance(other, Currencies):    
            for k, other_currency in other.data.items():
                if k in new_data:
                    new_data[k] = new_data[k] - other_currency
                else:
                    new_data[k] = -copy(other_currency)
        elif isinstance(other, Currency):
            if other.unit_kind in new_data:
                new_data[other.unit_kind] = new_data[other.unit_kind] - other
            else:
                new_data[other.unit_kind] = copy(other)
        else:
            raise Exception(f"invalid other type to add: {other}")
        return Currencies(new_data)

    def __mul__(self, other):
        new_data = {}
        for k, my_currency in self.data.items():
            new_data[k] = copy(my_currency * other)
        return Currencies(new_data)

    def __neg__(self):
        new_data = {}
        for k, my_currency in self.data.items():
            new_data[k] = -my_currency
        return Currencies(new_data)