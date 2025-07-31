from decimal import Decimal
from serialize_context import SerializeContext
from util import to_dict


class WriteOption:
    ''' Tracks an option written and sold. '''

    def __init__(self, asset, mode, date, strike_price, n_contracts, price):
        self.asset = asset
        self.mode = mode
        self.date = date
        self.strike_price = strike_price
        self.n_contracts = n_contracts
        self.price = price

    def __repr__(self):
        price = self.price
        value = self.get_value()
        return f"{self.n_contracts} {self.date} ${self.strike_price:.2f} {self.mode}: ${price:.2f} x {self.n_contracts} x 100 = ${value:.2f}"
    
    def get_value(self):
        return self.price * self.n_contracts * 100

    def is_identical_security(self, other) -> bool:
        ''' Check if this and other would count as identical securities. '''

        return (self.asset == other.asset and self.mode == other.mode and 
                self.date == other.date and 
                self.strike_price == other.strike_price)
    
    def combine(self, other):
        ''' Combine the other WriteOption into this one, keeping the price of 
            this one. '''

        if self.asset != other.asset:
            raise Exception(f"Assets do not match: {self.asset} vs {other.asset}")
        if self.mode != other.mode:
            raise Exception(f"Modes do not match: {self.mode} vs {other.mode}")
        if self.date != other.date:
            raise Exception(f"Dates do not match: {self.date} vs {other.date}")
        if self.strike_price != other.strike_price:
            raise Exception(f"Strikes do not match: {self.strike_price} vs {other.strike_price}")

        self.n_contracts += other.n_contracts

    def get_serialize_id(self, context: SerializeContext):
        return context.new_str_id(self, "o")

    def to_dict(self, context: SerializeContext):
        return {
            "mode": self.mode,
            "date": self.date,
            "strikePrice": self.strike_price,
            "nContracts": self.n_contracts,
            "price": self.price,
            "id": self.get_serialize_id(context)
        }
    

def new_write_option_from_dict(d, ctx: SerializeContext) -> WriteOption:
    ''' Construct an option from the given dictionary. '''

    o = WriteOption(asset=ctx.asset, mode=d["mode"], date=d["date"],
            strike_price=d["strikePrice"], n_contracts=d["nContracts"], 
            price=Decimal(d["price"]))
    ctx.id_to_value[d["id"]] = o
    return o