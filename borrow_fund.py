from datetime import datetime
from decimal import Decimal
from serialize_context import SerializeContext
from util import currency_collection_to_string, add_to_currency_collection, get_currency_from_collection


# Normal level for reserve fund.
reserve_normal_level = {'usd': 20000}

# Threshold of money in the income pile where the fund is considered ready to
# guarantee the next borrow. If the income pile drops below this threshold, 
# priority should be given to recharge it.
income_danger_threshold = {'usd': 4000}

# Threshold of money in the income pile where if the fund drops below this, 
# profits will have a tax applied to them that will be contributed to the fund.
income_tax_threshold = {'usd': 6000}

# If income fund is below tax threshold, trading profits are taxed at this rate.
income_tax_rate = 0.1

class BorrowFund:
    ''' A special fund of money (still intermingled with trading assets)
        designed for paying the costs associated with borrowing and repaying
        shares. 
    '''

    def __init__(self, account, income, reserves, loaned):
        self.account = account
        self.income = income
        self.reserves = reserves
        self.loaned = loaned

    def update(self):
        self.loaned = {}
        for asset in self.account.pf.assets:
            for e in asset.borrow_events:
                add_to_currency_collection(self.loaned, e.funding, 
                    asset.currency_kind)

    def is_in_danger(self, currency_kind):
        ''' For the given currency, if income fund drops below threshold, it is 
            considered to be in danger. '''
        
        if currency_kind not in income_danger_threshold:
            return Decimal(0)
        else:
            threshold = income_danger_threshold[currency_kind]
            return self.income[currency_kind] < threshold

    def is_taxed(self, currency_kind):
        ''' For the given currency, if income fund drops below threshold, it is 
            considered to be taxed. Note that it could also be in danger. '''
        
        if currency_kind not in income_danger_threshold:
            return Decimal(0)
        else:
            threshold = income_tax_threshold[currency_kind]
            return self.income[currency_kind] < threshold

    def get_income_ready_room(self, currency_kind):
        ''' How much money is left in income to reach the readiness threshold. '''

        if currency_kind not in income_danger_threshold:
            return Decimal(0)
        else:
            threshold = income_danger_threshold[currency_kind]
            have = self.income[currency_kind] if currency_kind in self.income else Decimal(0)
            return max(threshold - have, Decimal(0))

    def add_income(self, amount, currency_kind):
        if currency_kind not in self.income:
            self.income[currency_kind] = amount
        else:
            self.income[currency_kind] += amount
        print(f"Adding ${amount:.2f} {currency_kind} to borrow income fund => ${self.income[currency_kind]:.2f}")

    def add_reserves(self, amount, currency_kind):
        if currency_kind not in self.reserves:
            self.reserves[currency_kind] = amount
        else:
            self.reserves[currency_kind] += amount
        print(f"Adding ${amount:.2f} {currency_kind} to borrow reserve fund => ${self.reserves[currency_kind]:.2f}")

    def add_loan(self, amount, currency_kind):
        if currency_kind not in self.loaned:
            self.loaned[currency_kind] = amount
        else:
            self.loaned[currency_kind] += amount
        print(f"Adding ${amount:.2f} {currency_kind} to borrow loan => ${self.loaned[currency_kind]:.2f}")

    def correct_borrow_reserve(self):
        ''' Reset borrow reserve to its normal level, adding or removing from
            the income fund to do so. '''
        for (currency_kind, normal_level) in reserve_normal_level.items():
            reserve_amount = get_currency_from_collection(self.reserves, 
                currency_kind=currency_kind)

            needed = normal_level - reserve_amount
            print("needed", needed)
            print("has", reserve_amount)
            self.add_reserves(needed, currency_kind=currency_kind)
            self.add_income(-needed, currency_kind=currency_kind)

    def to_dict(self, context: SerializeContext):
        return {
            "income": self.income,
            "reserves": self.reserves,
            "loaned": self.loaned
        }
    
    def __repr__(self):
        return f"Borrow[inc: {currency_collection_to_string(self.income)}; loan: {currency_collection_to_string(self.loaned)}; res: {currency_collection_to_string(self.reserves)}]"


def new_borrow_fund_from_dict(dictionary) -> BorrowFund:
    raw_income = dictionary["income"]
    raw_reserves = dictionary["reserves"]
    raw_loaned = dictionary["loaned"]
    income = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_income.items()
    }
    reserves = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_reserves.items()
    }
    loaned = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_loaned.items()
    }

    return BorrowFund(None, income=income, reserves=reserves,
        loaned=loaned)

