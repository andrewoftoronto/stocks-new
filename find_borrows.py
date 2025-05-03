from decimal import Decimal
from util import penny_round
from pf import start
from math import ceil
from option_pricing import OptionPricing
from option import UpgradeTarget


option_data = [
    ['PUT', '2025-09-19', 50, 52, 9.19],
    ['PUT', '2025-09-19', 50, 49, 10.33],
    ['PUT', '2025-09-19', 50, 45, 12.06],
    ['PUT', '2025-09-19', 50, 40, 14.61],
    ['PUT', '2025-09-19', 50, 35, 17.63],
    ['PUT', '2025-09-19', 50, 30, 21.14],
    ['PUT', '2025-09-19', 50, 25, 25.14]
]


def find_borrows(p, a):

    a.update(True)

    # Estimated value of other assets we can sell.
    extra_equity = Decimal(0.0)

    # Extra room allowed from margin.
    #extra_equity += Decimal(13620.03)

    #p.account.currencies['usd'] += Decimal(34186)

    a.option_pricing = OptionPricing(option_data)

    # If no options are held, this is the last price that a borrow happened.
    borrow_point = None

    while a.price > 10:

        '''best_option_to_sell = None
        potential_option_gain = None
        for option in a.options:
            a.option_pricing.update_price(option, a.price)
            this_gain = option.price * option.n_contracts * 100 - option.buy_cost
            if potential_option_gain is None or potential_option_gain < this_gain:
                potential_option_gain = this_gain
                best_option_to_sell = option
        '''
                
        if (p.margin_available() < Decimal(1000.0)):
            return

            if len(a.options) > 0:
                a.sell_option(best_option_to_sell, best_option_to_sell.n_contracts)

            buy_needed_options(a, 1.2)

            if borrow_point is not None:
                borrow_point = a.price

            amount_to_free = 20000
            n_to_borrow = ceil(amount_to_free / a.price) 
            a.borrow(n_to_borrow)
            borrow_point = a.price
            print(f"Borrowing {n_to_borrow} @ {a.price:.2f}")
            print(p)

            a.update()
            if a.price < 27:
                return

        a.price = penny_round(Decimal(a.price) / Decimal(1.01) - Decimal(0.01))
        a.update()


def buy_needed_options(a, strike_level: float):
    
    asset_buy_price = a.price
    approx_strike = Decimal(float(a.price) / strike_level)
    borrow_at = Decimal(float(a.price) / strike_level / 1.2)

    strike = a.option_pricing.lower_strike('PUT', '2025-09-19', approx_strike)
    buy_price = a.option_pricing.find('PUT', '2025-09-19', strike, asset_buy_price)
    borrow_price = a.option_pricing.find('PUT', '2025-09-19', strike, borrow_at)
    n_needed = 4000 / float(borrow_price - buy_price)
    n_contracts = ceil(n_needed / 100.0)
    print(f"{approx_strike:.2f}:{borrow_at:.2f}")
    print(f"{buy_price:.2f}:{borrow_price:.2f}:{n_contracts}")

    o = a.buy_option('PUT', '2025-09-19', strike, n_contracts, price=buy_price)
    
    price_asset_upgrade_time = Decimal(float(approx_strike) * 1.2 * 1.2 * 1.2)
    upgrade_price = a.option_pricing.find('PUT', '2025-09-19', strike,
            price_asset_upgrade_time)
    o.upgrade_targets = [UpgradeTarget(price_asset_upgrade_time, upgrade_price)]
    print(o, o.upgrade_targets)


if __name__ == '__main__':

    p = start()
    a = p.assets[0]
    find_borrows(p, a)

    a.summarize(True)