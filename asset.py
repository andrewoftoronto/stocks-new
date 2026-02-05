import random
import string
from option import option_from_dict
from util import list_from_dict, read_from_dict, fixup_price
from segregated_shares import SegregatedShares, new_empty_segregated_shares, new_segregated_shares_from_dict
from currency import Currency, currency_from_dict, currency_from_common
from option import Option
from shares import Shares, new_empty_shares
from distribute import distribute, DistributionReport

# How many times higher in value the current price must be to be allowed to sell
# a share.
MIN_SELL_GAIN = 1.01

# Index of segregated share account containing unbound shares.
UNBOUND_SHARES = 0

# Index of segregated share account containing bound shares.
BOUND_SHARES = 1

# Index of segregated share account containing shares reserved for expanding
# the horizon.
HORIZON_SHARES = 2

# Index of segregated share account containing shares reserved for use as
# collateral.
COLLATERAL_SHARES = 3

# Index of segregated share account for manual use, excluding it from being
# used to cover targets, etc.
MANUAL_SHARES = 4

N_SHARE_GROUPS = 5

class Asset:
    def __init__(self, p, data_dict=None):
        from component import load_components_from_dict

        self.p = p
        self.options = list_from_dict(data_dict, 'options', option_from_dict)
        self.shares = new_segregated_shares_from_dict(data_dict, N_SHARE_GROUPS)
        self.currency_kind = read_from_dict('currencyKind', data_dict, 'USD')
        self.price = load_price_from_dict(data_dict, self.currency_kind)
        self.components = load_components_from_dict(p, self, data_dict, 'components')
        self.cached_targets = None
        self.cached_assignments = None

    def get_target_assignment(self, target):
        if self.cached_assignments is None or target not in self.cached_assignments:
            self.recompute_assignments()
        
        if target not in self.cached_assignments:
            return new_empty_shares(self.currency_kind)
        else:
            return self.cached_assignments[target]

    def get_option_by_id(self, option_id):
        ''' Get an option using its id.'''

        for option in self.options:
            if option.option_id == option_id:
                return option
        return None

    def buy_option(self, mode, date, strike_price, n_contracts, price=None,
            theta=None) -> Option:
        ''' Buy a new option. '''

        self.p.push_action('Buy Option')
        self.fixup_price()

        price = fixup_price(price, self.currency_kind)
        option = Option(data_dict={
            'currencyKind': self.currency_kind,
            'mode': mode,
            'date': date,
            'strikePrice': strike_price,
            'nContracts': n_contracts,
            'price': price,
            'theta': theta,
        })

        # Check if an identical option exists to combine with.
        identical_found = False
        for other_option in self.options:
            if other_option.is_identical_security(option):
                other_option.combine(option)
                option = other_option
                option.price = price
                identical_found = True
                break
        
        if not identical_found:
            self.options.append(option)
            option.option_id = self._generate_option_id()

        buy_cost = n_contracts * 100 * price
        print("BUY COST", buy_cost)
        print("OPTION PREVIOUS BUY COST", option.buy_cost)
        self.p.account.money -= buy_cost
        option.buy_cost += buy_cost

        self.p.record_action_post_state()
        return option

    def sell_option(self, option, n_contracts=None, price=None):
        ''' Sell an option. '''

        self.p.push_action('Sell Option')
        self.fixup_price()

        price = fixup_price(price, self.currency_kind)
        self.p.account.money += n_contracts * 100 * price

    def save(self, file_name: str):
        context = SerializeContext()
        fio.save(file_name, self.to_dict(context))

    def fixup_price(self):
        ''' Fixes up the price to be a proper Currency value. '''
        self.price = fixup_price(self.price, self.currency_kind)

    def n_physical_shares(self) -> int:
        return len(self.shares) - self.n_borrowed()

    def __len__(self) -> int:
        return len(self.shares)

    def _generate_option_id(self) -> str:
        ''' Generate a short ID for options, ensuring no collisions. '''
        
        while True:
            characters = string.ascii_lowercase + string.digits
            generated_id = [random.choice(characters) for i in range(0, 3)]
            generated_id = ''.join(generated_id)

            existing_option = self.get_option_by_id(generated_id)
            if existing_option is None:
                return generated_id
        raise Exception("Failed to generate ID")

    def _gather_targets(self):
        ''' Collect targets from the different components. '''

        targets = []
        for component in self.components:
            targets += component.get_targets()
        self.cached_targets = targets
        
    def _recompute_assignments(self, all_shares=None) -> DistributionReport:
        ''' Recompute assignment of shares to targets. '''

        print("Current price:", self.price)

        self._gather_targets()
        
        if all_shares is None:
            all_shares = self.shares[UNBOUND_SHARES] + self.shares[BOUND_SHARES]
        report = distribute(all_shares, self.cached_targets, self.price, 
                MIN_SELL_GAIN)
        self.shares[UNBOUND_SHARES] = report.unbound_shares
        self.shares[BOUND_SHARES] = all_shares - report.unbound_shares

        self.cached_assignments = report.target_to_assignment
        return report


def load_price_from_dict(data_dict, currency_kind):
    if data_dict is None:
        return Currency(0, currency_kind)
    
    price = data_dict['price']
    if isinstance(price, dict):
        return currency_from_dict(price)
    else:
        return currency_from_common(price, currency_kind)
    if 'price' in data_dict:
        return Currency()
        
        