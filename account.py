import fio
from datetime import datetime
from decimal import Decimal
from util import to_dict, currency_collection_to_string, penny_round, add_to_currency_collection
from serialize_context import SerializeContext
from borrow_fund import new_borrow_fund_from_dict
from zoneinfo import ZoneInfo
from math import ceil


daily_borrow_fund_contributions = {'usd': 20}


class Account:
    ''' Money, etc. related to the total trading account. '''

    def __init__(self, pf, currencies, profit_counter, daily_profit_counter, 
            borrow_fund, last_checked=None):
        self.pf = pf
        self.currencies = currencies
        self.daily_profit_counter = daily_profit_counter
        self.profit_counter = profit_counter
        self.borrow_fund = borrow_fund
        self.last_checked = last_checked

    def __repr__(self):
        return (f"$: {currency_collection_to_string(self.currencies)}, " +
            f"profit: {currency_collection_to_string(self.profit_counter)}, " +
            f"dailyProfit: {currency_collection_to_string(self.daily_profit_counter)}, " +
            f"{self.borrow_fund}")

    def to_dict(self, context: SerializeContext):
        return {
            "currencies": self.currencies,
            "profitCounter": self.profit_counter,
            "dailyProfitCounter": self.daily_profit_counter,
            "borrowFund": self.borrow_fund.to_dict(context),
            "lastChecked": None if self.last_checked is None else self.last_checked.isoformat()
        }
    
    def save(self, file_name):
        context = SerializeContext()
        fio.save(file_name, self.to_dict(context))

    def add_profit(self, change, currency='usd'):
        ''' Add the given change value to the profit. You can use a negative
            value to reduce the profit. '''

        change = Decimal(change)
        add_to_currency_collection(self.profit_counter, change, currency)
        add_to_currency_collection(self.daily_profit_counter, change, currency)

    def reset_profit(self):
        ''' Reset the cumulative profit counter of this account. '''

        self.profit_counter = {}

    def update(self):
        now = datetime.now(ZoneInfo("America/Toronto"))
        date_diff = now.date() - self.last_checked.date()
        n_days = date_diff.days
        self.last_checked = now

        self.borrow_fund.update()

        if n_days > 0:

            if n_days > 1:
                self.apply_update(n_days - 1)

            print("Resetting daily profit counter")
            self.daily_profit_counter = {}

            self.apply_update(1)


    def apply_update(self, n_days: int):
        print(f"Applying {n_days} days of updates and costs")

        # Account for option depreciation as a cost, reducing profit.
        # We reduce option cost with option depreciation since the cost is
        # already being accounted for by reducing profit.
        daily_depreciation = Decimal(0)
        for asset in self.pf.assets:
            for option in asset.options:
                if option.theta > 0:
                    raise Exception("Theta should be negative")

                option_decay_depreciation = option.theta * option.n_contracts * 100 
                daily_depreciation += option_decay_depreciation
                option.buy_cost += penny_round(option_decay_depreciation * n_days)
        self.add_profit(daily_depreciation * n_days)
        print(f"Daily Option Depreciation: {daily_depreciation:.2f}")

        # Account for share price decay, reducing profit.
        decay_cost = Decimal(0)
        for asset in self.pf.assets:
            asset_decay_cost = asset.apply_decay(n_days)
            decay_cost += asset_decay_cost
        self.add_profit(-decay_cost)
        print(f"Daily Decay Cost: {(decay_cost / n_days):.2f}")

        # Contribute to the borrow fund.
        for (currency_kind, amount) in daily_borrow_fund_contributions.items():
            d_money = amount * n_days
            self.borrow_fund.add_loan(-d_money, currency_kind)
            self.add_profit(-d_money, currency_kind)

        # Tick borrow prices up that are (or close to being) due.
        borrow_adjust_cost = Decimal(0)
        for asset in self.pf.assets:
            for borrow_event in asset.borrow_events:

                # Don't affect borrow events still far ahead in price.
                if asset.price * Decimal(1.05) < borrow_event.rebuy_at:
                    continue

                share_price_change = penny_round(borrow_event.rebuy_at * Decimal(0.0003), fn=ceil)
                borrow_event.rebuy_at += share_price_change * n_days

                d_money = share_price_change * borrow_event.n_shares * n_days
                borrow_adjust_cost += d_money
        self.add_profit(-borrow_adjust_cost)
        print(f"Borrow Adjust Cost: {borrow_adjust_cost / n_days:.2f}")


def new_account_from_dict(dict, context: SerializeContext):
    ''' With the given dict, creates an Account object. '''

    raw_currencies = dict["currencies"]
    currencies = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_currencies.items()
    }

    raw_profit_counter = dict["profitCounter"]
    profit_counter = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_profit_counter.items()
    }

    raw_daily_profit_counter = dict["dailyProfitCounter"]
    daily_profit_counter = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_daily_profit_counter.items()
    }

    borrow_fund = new_borrow_fund_from_dict(dict['borrowFund'])
    last_checked = datetime.fromisoformat(dict["lastChecked"])

    account = Account(context.pf, currencies, profit_counter, 
        daily_profit_counter, borrow_fund, last_checked=last_checked)
    borrow_fund.account = account
    return account