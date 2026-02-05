from datetime import datetime

from shares import new_shares_from_common
from sub_account import SubAccount
from lambda_account import LambdaAccount
from currency import Currency
from currencies import Currencies
from option_component import OptionComponent
from util import fixup_currencies


DEFAULT_CURRENCY_KIND = 'USD'


class Account:

    def __init__(self, pf, accounts_dict=None):

        def new_sub_account(id, name):
            if accounts_dict is not None:
                return SubAccount(id, name, proto=accounts_dict[id])
            else:
                return SubAccount(id, name, proto=None)

        self.pf = pf

        self.money = new_sub_account('money', "Money")

        # Total profit made from various activities like selling shares.
        self.gross_profit = new_sub_account('gross-profit', 'Gross Profit')
        # Profit disbursed for other purposes.
        self.disbursed_profit = new_sub_account('disbursed-profit', 'Disbursed Profit')
        
        # Loss from selling options for less than paid, excluding what was
        # accounted for in depreciation or upgrade funding.
        self.option_loss = new_sub_account('option-loss', 'Option Loss')
        # Tracks total money used to cover loss in option value via theta 
        # decay. For example, some profit may be moved daily to cover the 
        # reduction in option value due to theta decay. 
        self.option_depreciation = new_sub_account('option-depreciation', 
            'Option Depreciation')
        # Money used to cover the cost of upgrading options to a higher level
        # of protection (e.x $40 PUT -> $50 PUT). For example, we can buy
        # extra shares beforehand and sell them at upgrade time, directing the
        # profit toward covering this cost and preventing it from showing up
        # as option_loss.
        self.option_upgrade_fund = new_sub_account('option-upgrade-fund', 
            'Option Upgrade Fund')
        
        # Total loss from rebuying shares for higher than their rebuy price.
        self.borrow_loss = new_sub_account('borrow-loss', 'Borrow Loss')
        # Total surplus from rebuying shares for lower than their rebuy price.
        self.borrow_surplus = new_sub_account('borrow-surplus', 'Borrow Surplus')
        # Extra money added to be marked for borrow purposes.
        self.borrow_extra = new_sub_account('borrow-extra', 'Borrow Extra')
        # Borrow funds disbursed for other purposes.
        self.disbursed_borrow_funds = new_sub_account('disbursed-borrow-funds', 
            'Disbursed Borrow Funds')

        # Combines all losses into a single line item.
        self.losses = LambdaAccount(
            lambda: self.borrow_loss.total() + self.option_loss.total()
        )
        # Net profit after factoring in disbursed funds and losses.
        self.net_profit = LambdaAccount(
            lambda: self.gross_profit.total() - self.disbursed_profit.total() - 
            self.losses.total()
        )

        now = datetime.now()
        self.last_checked = datetime.fromisoformat(accounts_dict['lastChecked']) if accounts_dict is not None else now.date()

    def to_dict(self):
        pass

    def add_profit(self, profit):
        if isinstance(profit, Currencies):
            self.gross_profit += profit
        else:
            self.gross_profit += Currency(profit, DEFAULT_CURRENCY_KIND)

    def spend_profit(self, amount, dest_account):
        if amount.has_negative():
            raise Exception(f"Attempting to spend negative amount of profit: {amount}")

        amount = fixup_currencies(amount, DEFAULT_CURRENCY_KIND)
        self.disbursed_profit -= amount
        dest_account += amount

    def update(self):
        now = datetime.now(ZoneInfo("America/Toronto"))
        date_diff = now.date() - self.last_checked.date()
        n_days = date_diff.days
        self.last_checked = now

        if n_days > 0:
            if n_days > 1:
                self.apply_update(n_days - 1)

            self.apply_update(1)

    def apply_update(self, n_days: int):
        print(f"Applying {n_days} days of updates and costs")

        # Account for option depreciation as a cost, reducing profit.
        # We reduce option cost with option depreciation since the cost is
        # already being accounted for by reducing profit.
        daily_depreciation = Currencies()
        for asset in self.pf.assets:
            currency_kind = asset.currency_kind
            for option in asset.options:
                if option.theta is None:
                    print(f"WARNING: Option {option} has null theta")
                    continue
                elif 0 < option.theta:
                    raise Exception("Theta should be negative")

                option_decay_depreciation = option.theta * option.n_contracts * 100
                daily_depreciation += Currency(int(round(option_decay_depreciation)), currency_kind)
                option.buy_cost += Currency(int(round(option_decay_depreciation * n_days)), currency_kind)
        self.spend_profit(-daily_depreciation * n_days, self.option_depreciation)
        print(f"Daily Option Depreciation: {daily_depreciation}")

        # Account for share depreciation.
        share_depreciation = Currencies()
        for asset in self.pf.assets:
            currency_kind = asset.currency_kind
            


if __name__ == '__main__':
    from pf import Portfolio
    from asset import Asset
    from currency import currency_from_common
    from option import OptionUpgradeTarget

    acc = Account(pf=None)

    p = Portfolio(acc)
    a = Asset(p)
    p.assets = [a]

    acc.pf = p

    opt_component = OptionComponent(p, a)
    a.components.append(opt_component)

    a.price = 13.73
    o = a.buy_option('CALL', '2025-11-23', 15, 1, 5.29, theta=-0.024)
    print("Buy cost: ", o.buy_cost)
    o.upgrade_targets = [OptionUpgradeTarget(30, 3.14)]

    acc.apply_update(1)
    print('Profit Remaining:', acc.gross_profit.total() - acc.disbursed_profit.total())
    print('Total Option depreciation:', acc.option_depreciation)

    print(a.price)
    print(a.options[0])
    print("Money:", acc.money)

    opt_component.update()
    t = opt_component.option_to_targets[o][0]
    print(f"Target: {t.profit}")
    a._gather_targets()
    report = a._recompute_assignments()
    print(report.buys_needed)
    print(a.cached_assignments[t].pairs)
    opt_component.sell_target(t)

    print(f"Now opt {o.upgrade_funding} funding.")