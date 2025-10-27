from datetime import datetime
from decimal import Decimal
from serialize_context import SerializeContext
from util import currency_collection_to_string, subtract_currency_collections, add_to_currency_collection, get_currency_from_collection


# When amount owing exceeds this, tax trading profits.
tax_threshold = {'usd': -2000}

# If income fund is below tax threshold, trading profits are taxed at this rate.
income_tax_rate = 0.1


class BorrowFund:
    ''' Special fund of money (still intermingled with trading assets) designed
        for paying the costs associated with borrowing and repaying shares. 
    '''

    def __init__(self, account, loan_balance, promised_share_balance=Decimal(0)):
        self.account = account
        self.loan_balance = loan_balance
        self.promised_share_balance = promised_share_balance

    def update(self):
        from asset import PROMISE_SHARES

        self.promised_share_balance = {}
        for asset in self.account.pf.assets:
            profit = Decimal(0)
            promise_shares = asset.shares[PROMISE_SHARES]
            for pair in promise_shares.pairs:
                per_profit = pair[0] * Decimal(1.2) - pair[0]
                qty = pair[1]
                profit += per_profit * qty

            add_to_currency_collection(self.promised_share_balance, profit, 
                    asset.currency_kind)        

    def uncovered_balance(self):
        uncovered = subtract_currency_collections(self.loan_balance, self.promised_share_balance)
        return uncovered

    def is_taxed(self, currency_kind):
        ''' For the given currency, if the un-covered loan balance exceeds this
            value, then profits will be taxed.  '''
        
        if currency_kind not in tax_threshold:
            return Decimal(0)
        else:
            threshold = tax_threshold[currency_kind]
            uncovered_balance = self.uncovered_balance()
            return threshold < uncovered_balance[currency_kind]

    def add_loan(self, amount, currency_kind):
        if currency_kind not in self.loan_balance:
            self.loan_balance[currency_kind] = amount
        else:
            self.loan_balance[currency_kind] += amount
        print(f"Adding ${amount:.2f} {currency_kind} to borrow loan => ${self.loan_balance[currency_kind]:.2f}")

    def to_dict(self, context: SerializeContext):
        return {
            "loanBalance": self.loan_balance,
            "promisedShareBalance": self.promised_share_balance,
        }
    
    def __repr__(self):
        uncovered = currency_collection_to_string(self.uncovered_balance())
        promised_share_balance = currency_collection_to_string(self.promised_share_balance)
        return f"Borrow[uncovered-loan: {uncovered}; promisedShareBalance: {promised_share_balance}]"


def new_borrow_fund_from_dict(dictionary) -> BorrowFund:
    raw_loan_balance = dictionary["loanBalance"]
    raw_promised_share_balance = dictionary["promisedShareBalance"]
    loan_balance = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_loan_balance.items()
    }
    promised_share_balance = {
        symbol: Decimal(value) 
        for (symbol, value) in raw_promised_share_balance.items()
    }
    return BorrowFund(
        None, 
            loan_balance=loan_balance, 
            promised_share_balance=promised_share_balance
    )

