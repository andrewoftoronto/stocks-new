from decimal import Decimal
from serialize_context import SerializeContext
import uuid


class Target:
    ''' A target that determines at which price to sell some shares and how 
        much profit it should seek to make.
    '''

    def __init__(self, name: str, profit: Decimal, sell_price: Decimal, 
            max_buy_price: Decimal, min_buy_price: Decimal,
            horizon_request_id = None):

        # Human-readable name used to identify this target.
        self.name = name

        # Amount of profit needed to satisfy this target.
        self.profit = profit

        # Price at which to sell. 
        self.sell_price = sell_price

        # Maximum price of shares that can be assigned to this target.
        self.max_buy_price = max_buy_price

        # Minimum price of shares that can be assigned to this target and get
        # full credit. Any shares assigned to this target that are of lower
        # price will get only as much credit as (sell_price - min_buy_price).
        self.min_buy_price = min_buy_price

        # Tracks whether this target is requesting horizon funding. If 
        # non-null, this target is seeking to be funded out of the horizon
        # fund. This essentially tracks the ID of the request and will be set
        # to None when the request has been satisfied.
        self.horizon_request_id = horizon_request_id

    def apply_decay_fn(self, decay_fn):
        self.sell_price = decay_fn(self.sell_price)
        self.max_buy_price = decay_fn(self.max_buy_price)
        self.min_buy_price = decay_fn(self.min_buy_price)
    
    def to_dict(self, context: SerializeContext):
        return {
            "id": context.new_str_id(self, "t"),
            "name": self.name,
            "profit": self.profit,
            "sell_price": self.sell_price,
            "max_buy_price": self.max_buy_price,
            "min_buy_price": self.min_buy_price,
            "horizon_request_id": self.horizon_request_id
        }

    def __repr__(self):
        return (f"Target[name: {self.name}, "
            f"profit: {self.profit:.2f}, " +
            f"sellPrice: {self.sell_price:.2f}, " +
            f"maxBuyPrice: {self.max_buy_price:.2f}, " +
            f"minBuyPrice: {self.min_buy_price:.2f}]" +
            f"horizonFundID: {self.horizon_request_id}]")

def new_target_from_dict(dict, context: SerializeContext) -> Target:
    ''' Loads a Target from the given dict. '''

    id = dict["id"]
    name = dict["name"]
    profit = Decimal(dict["profit"])
    sell_price = Decimal(dict["sell_price"])
    max_buy_price = Decimal(dict["max_buy_price"])
    min_buy_price = Decimal(dict["min_buy_price"])
    horizon_request_id = dict.get("horizon_request_id", None)

    target = Target(name, profit, sell_price, max_buy_price, min_buy_price,
            horizon_request_id=horizon_request_id)
    context.id_to_value[id] = target
    return target