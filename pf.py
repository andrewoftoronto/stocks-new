from decimal import Decimal
import os
import fio
from util import to_dict, combine_currency_collections
from asset import Asset, new_asset_from_dict, write_target_log
from account import Account, new_account_from_dict
from serialize_context import SerializeContext
from copy import deepcopy
from util import penny_round


# Wealthsimple uses bid price for holding value calculations.
OPTION_BID_TOLERANCE = 0.93
ASSET_BIND_TOLERANCE = 0.9975

# Not sure what wealthsimple does but margin requirement seems slightly 
# inflated compared to expectation, so I simulate some tolerance.
MARGIN_REQUIREMENT_TOLERANCE = 1.00


class Portfolio:
    def __init__(self):
        context = SerializeContext()
        context.pf = self

        self.account = load_account("assets/account.json", context)

        filter_fn = lambda f: f.endswith('.json') and f != "account.json"

        file_names = os.listdir("assets/")
        file_names = list(filter(filter_fn, file_names))
        self.assets = []
        self.checkpoints = []
        for file_name in file_names:
            asset = load_asset(f"assets/{file_name}", self, context)
            self.assets.append(asset)
        self.assets = sorted(self.assets, key=lambda a: a.order)

    def make_checkpoint(self):
        ''' Creates a checkpoint dictionary of the current portfolio. '''
        context = SerializeContext()
        asset_dict = to_dict(self.assets, context)
        return {
            "account": self.account.to_dict(context),
            "assets": asset_dict
        }
    
    def checkpoint(self):
        ''' Adds a checkpoint to the stack. '''
        self.checkpoints.append(self.make_checkpoint())

    def undo(self):
        ''' Rewinds the state of the portfolio to the last checkpoint. '''
        c = self.checkpoints.pop()
        context = SerializeContext()
        context.pf = self
        self.account = new_account_from_dict(c["account"], context)
        
        for (i, raw_asset) in enumerate(c["assets"]):
            self.assets[i].replace_from_dict(raw_asset, context)

    def save(self):
        ''' Saves the current state of the portfolio. '''

        self.account.save("assets/account.json")
        for asset in self.assets:
            asset.save(f"assets/{asset.name}.json")

    def new_asset(self, name, order, price, currency_type):
        asset = Asset(name, order, price, currency_type, None, self, 0)
        self.assets.append(asset)

    def balance(self, currency):
        amount = self.account.currencies[currency]
        for asset in self.assets:
            if asset.currency_kind == currency:
                amount += asset.n_physical_shares() * Decimal(asset.price)
        return penny_round(amount)

    def cash(self, currency_kind='usd'):
        total = 0.0
        for (k, v) in self.account.currencies.items():
            v = float(v)
            if k == 'cad':
                v = v * 0.7

            total += v

        return Decimal(total)

    def holdings(self, currency_kind='usd'):
        if currency_kind != 'usd':
            raise Exception("not implemented")

        holdings = Decimal(0)
        for asset in self.assets:
            if asset.currency_kind != 'usd':
                raise Exception("not supported")

            holdings += Decimal(float(asset.price) * len(asset) * ASSET_BIND_TOLERANCE)
            for option in asset.options:
                holdings += Decimal(float(option.price) * option.n_contracts * 100 * OPTION_BID_TOLERANCE)

        return penny_round(holdings)

    def margin_requirement(self, currency_kind='usd'):
        if currency_kind != 'usd':
            raise Exception("not implemented")
        
        r = 0
        for asset in self.assets:
            if asset.currency_kind != 'usd':
                raise Exception("not supported")
            
            r += float(asset.price) * len(asset) * float(asset.margin_requirement)
            for option in asset.options:
                r += float(option.price) * option.n_contracts * 100

        return Decimal(r * MARGIN_REQUIREMENT_TOLERANCE)

    def margin_available(self, currency_kind='usd'):
        if currency_kind != 'usd':
            raise Exception("not implemented")

        return self.holdings(currency_kind) + self.cash(currency_kind) - self.margin_requirement()

    def total_borrow_funding(self):
        borrow_funds = deepcopy(self.account.borrow_fund.income)
        borrow_funds = combine_currency_collections(borrow_funds, self.account.borrow_fund.reserves)
        
        # Event loans are not segregated from the borrow reserve fund. So here,
        # we just need to include event repayment funding.
        for asset in self.assets:
            for event in asset.borrow_events:
                amount = event.repay
                currency = asset.currency_kind
                borrow_funds[currency] += amount
        
        return borrow_funds

    def add_profit(self, change: Decimal, currency='usd'):
        self.account.add_profit(change, currency)

    def add_borrow_funding(self, change: Decimal, currency='usd'):
        self.account.borrow_fund.add_income(change, currency)

    def update(self):
        self.account.update()

    def __repr__(self) -> str:
        text = str(self.account) + "\n"
        text += f"Margin Available: ${self.margin_available():.2f}; Margin Requirement: ${self.margin_requirement():.2f}\n"
        for asset in self.assets:
            asset.fixup_price()
            price = asset.price
            n_shares = len(asset.shares)
            n_physical_shares = asset.n_physical_shares()

            if asset.cached_target_to_assignment is None:
                asset.distribute()

            target_log = ""
            if len(asset.cached_targets) > 0:
                first_target = asset.cached_targets[0]
                target_log = write_target_log(first_target, None)
            text += f"{n_physical_shares} ({n_shares}) {asset.name} x ${price:.2f} [{target_log}]\n"
        return text


def load_account(file_name, context: SerializeContext) -> Account:
    ''' Loads Account details from the given file. '''

    file_name = "assets/account.json"
    dict = fio.load(file_name, True)
    if dict is not None:
        return new_account_from_dict(dict, context)
    else:
        return Account(context.pf, {'cad': 0, 'usd': 0},  {'cad': 0, 'usd': 0},
                 {'cad': 0, 'usd': 0}, None)
    

def load_asset(file_name, portfolio: Portfolio, context: SerializeContext) -> Asset:
    ''' Loads an Asset from the given file. '''

    dict = fio.load(file_name, False)
    return new_asset_from_dict(dict, portfolio, context)


def start() -> Portfolio:
    ''' Start up the portfolio. '''
    return Portfolio()