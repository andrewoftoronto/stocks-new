from util import read_from_dict, read_from_partial_dict, fixup_price
from util import read_from_dict


class Target:
    def __init__(self,  data_dict=None):
        self.sell_price = read_from_dict('sellPrice', data_dict) 
        self.profit = read_from_dict('profit', data_dict)
        self.min_buy_price = read_from_dict('minBuyPrice', data_dict)
        self.max_buy_price = read_from_dict('maxBuyPrice', data_dict)


def load_target(data_dict, serialize_context):
    return load_target(data_dict)