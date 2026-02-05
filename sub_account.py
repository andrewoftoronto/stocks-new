from copy import deepcopy
from currencies import Currencies


class SubAccount:
    ''' Tracks money put to a certain cause. '''

    def __init__(self, id, name, currencies=None, proto=None):
        self.id = id
        self.name = name

        if currencies is None:
            currencies = Currencies()
        self.currencies = currencies
        
        if proto is not None:
            self.currencies = deepcopy(proto.currencies)

    def total(self):
        return self.currencies

    def __iadd__(self, value):
        self.currencies = self.currencies + value
        return self

    def __isub__(self, other):
        self.currencies = self.currencies - other
        return self

    def __repr__(self):
        return f"{self.name} Account[{self.currencies}]"