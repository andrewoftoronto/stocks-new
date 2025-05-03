from decimal import Decimal
from pf import start

assets_and_targets = [(0, 90), (1, 55), (2, 185.5), (3, 40.0)]

p = start()
p.account.currencies['usd'] = Decimal(-60624.97)
print('initial:', p.balance('usd'))

for (asset_index, goal_price) in assets_and_targets:
    asset = p.assets[asset_index]
    asset.stages[1].horizon = Decimal(goal_price * 1.25)

    asset.update()

    while asset.price < goal_price:
        lowest_target = asset.cached_targets[0]

        borrows = sorted(asset.borrow_events, key=lambda x: x.price)
        lowest_borrow = borrows[0] if len(borrows) > 0 else None
        if lowest_borrow is None or lowest_target.sell_price < lowest_borrow.price:
            asset.price = lowest_target.sell_price
            asset.update(True)
        else:
            asset.price = lowest_borrow.price
            asset.unborrow(lowest_borrow.n_shares)

    print(p.balance('usd'))

