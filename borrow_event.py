from serialize_context import SerializeContext
from decimal import Decimal
from datetime import datetime


class BorrowEvent:
    ''' Tracks an event where shares were borrowed (sold) to free up money.
    
        Events can loan money from the borrow fund to allow rebuying the shares
        at a higher price than borrowed. They also track money being collected
        to repay that loan.
    '''

    def __init__(self, price, n_shares, date, cost, rebuy_at):
        self.price = Decimal(price)
        self.n_shares = n_shares
        self.date = date
        self.cost = cost
        self.rebuy_at = rebuy_at

    def to_dict(self, context: SerializeContext):
        return {
            "price": self.price,
            "nShares": self.n_shares,
            "date": self.date.isoformat(),
            "cost": self.cost,
            "rebuyAt": self.rebuy_at
        }
    
    def __repr__(self):
        return (f"[rebuyAt: {self.rebuy_at:.2f}, origPrice: {self.price:.2f}, " +
            f"nShares: {self.n_shares}, date: {self.date}, " +
            f"cost: {self.cost:.2f}]")
    

def new_borrow_event_from_dict(dictionary):
    price = Decimal(dictionary['price'])
    n_shares = dictionary['nShares']
    date = datetime.fromisoformat(dictionary['date'])
    cost = Decimal(dictionary['cost'])
    rebuyAt = Decimal(dictionary["rebuyAt"])
    return BorrowEvent(price, n_shares, date, cost, rebuy_at=rebuyAt)