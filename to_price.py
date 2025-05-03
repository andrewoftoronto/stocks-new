from decimal import Decimal
from util import penny_round
from pf import start
p = start()
a = p.assets[0]

target_price = Decimal(84.93)

# Estimated value of other assets we can sell.
#extra_equity = Decimal(10323.40)

#p.account.currencies['usd'] += extra_equity


def check_borrows(p, a):
    for (i, borrow_event) in enumerate(a.borrow_events):
        old_price = a.price
        if a.price > borrow_event[0] * 1.05:
           a.price = borrow_event[0]
           a.unborrow(borrow_event[1])
           a.price = old_price
    

a.update()
while a.price < target_price:

    check_borrows(p, a)

    next_target = a.cached_targets[0]
    next_price = next_target.sell_price
    if next_price > target_price:
        next_price = target_price

    a.price = next_price
    a.update(True)

a.summarize()