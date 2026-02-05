from decimal import Decimal


class Currency:
    def __init__(self, unit_value, unit_kind):
        self.unit_value = unit_value
        self.unit_kind = unit_kind

    def __repr__(self):
        return display(self.unit_value, self.unit_kind)

    def __add__(self, other):
        if other.unit_kind != self.unit_kind:
            raise Exception("Non-matching currency unit") 
        return Currency(self.unit_value + other.unit_value, self.unit_kind)

    def __sub__(self, other):
        if other.unit_kind != self.unit_kind:
            raise Exception("Non-matching currency unit") 
        return Currency(self.unit_value - other.unit_value, self.unit_kind)

    def __mul__(self, other):
        if isinstance(other, int):
            return Currency(self.unit_value * other, self.unit_kind)
        elif isinstance(other, float):
            new_unit_value = round(self.unit_value * other)
            return Currency(new_unit_value, self.unit_kind)
        else:
            raise Exception(f"Unsupported multiply other type: {other}")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __neg__(self):
        return Currency(-self.unit_value, self.unit_kind)

    def __lt__(self, other):
        if isinstance(other, int):
            return self.unit_value < other
        elif isinstance(other, Currency):
            if other.unit_kind != self.unit_kind:
                raise Exception("Non-matching currency unit") 
            return self.unit_value < other.unit_value
        else:
            raise Exception(f"Unsupported other type: {other}")

    
    def __le__(self, other):
        if isinstance(other, int):
            return self.unit_value <= other
        elif isinstance(other, Currency):
            if other.unit_kind != self.unit_kind:
                raise Exception("Non-matching currency unit") 
            return self.unit_value <= other.unit_value
        else:
            raise Exception(f"Unsupported other type: {other}")


    def __gt__(self, other):
        if isinstance(other, int):
            return self.unit_value > other.unit_value
        elif isinstance(other, Currency):
            if other.unit_kind != self.unit_kind:
                raise Exception("Non-matching currency unit") 
            return self.unit_value > other.unit_value
        else:
            raise Exception(f"Unsupported other type: {other}")


def currency_from_dict(data_dict):
    return Currency(data_dict['unitValue'], data_dict['unitKind'])


def currency_from_common(common_value, currency_kind):
    if currency_kind in ["CAD", 'USD']:
        return Currency(round(common_value * 100), currency_kind)
    else:
        raise Exception("Unknown currency unit")


def display(unit_value, unit_kind):
    if unit_kind in ['CAD', 'USD']:
        float_value = Decimal(unit_value) / Decimal(100.0)
        return f"${float_value:.2f} {unit_kind}"
    else:
        raise Exception("Unknown currency unit")