from serialize_context import SerializeContext
from decimal import Decimal
from datetime import datetime


class BorrowEvent:
    ''' Tracks an event where shares were borrowed (sold) to free up money.
    
        Events can loan money from the borrow fund to allow rebuying the shares
        at a higher price than borrowed. They also track money being collected
        to repay that loan.
    '''

    def __init__(self, price, n_shares, date, funding, repay=Decimal(0)):
        self.price = Decimal(price)
        self.n_shares = n_shares
        self.date = date
        self.funding = Decimal(funding)
        self.repay = repay

    def to_dict(self, context: SerializeContext):
        return {
            "price": self.price,
            "nShares": self.n_shares,
            "date": self.date.isoformat(),
            "funding": self.funding,
            "repay": self.repay
        }
    
    def get_max_rebuy(self):
        return self.price + self.funding / self.n_shares

    def __repr__(self):
        max_rebuy = self.get_max_rebuy()
        return (f"[maxRebuy: {max_rebuy:.2f}, price: {self.price:.2f}, " +
            f"nShares: {self.n_shares}, date: {self.date}, funding: {self.repay:.2f}/{self.funding:.2f}]")
    

def new_borrow_event_from_dict(dictionary):
    price = Decimal(dictionary['price'])
    n_shares = dictionary['nShares']
    date = datetime.fromisoformat(dictionary['date'])
    funding = Decimal(dictionary['funding'])
    repay = Decimal(dictionary["repay"])
    return BorrowEvent(price, n_shares, date, funding, repay=repay)