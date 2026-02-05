from util import read_from_dict, read_from_partial_dict, fixup_price
from currency import Currency
from serialize_context import SerializeContext


class Option:
    def __init__(self, data_dict=None):
        self.currency_kind = read_from_dict('currencyKind', data_dict)

        self.option_id = read_from_partial_dict('optionID', data_dict, None)
        self.mode = read_from_dict('mode', data_dict)
        self.date = read_from_dict('date', data_dict)
        self.strike_price = read_from_dict('strikePrice', data_dict)
        self.n_contracts = read_from_dict('nContracts', data_dict)
        self.price = read_from_dict('price', data_dict)
        self.theta = read_from_dict('theta', data_dict)
        self.buy_cost = read_from_partial_dict('buyCost', data_dict, Currency(0, self.currency_kind))
        self.upgrade_targets = read_from_partial_dict('upgradeTargets', data_dict, [])
        self.upgrade_funding = read_from_partial_dict('upgradeFunding', data_dict, Currency(0, self.currency_kind))

    def is_identical_security(self, other) -> bool:
        ''' Check if this and other would count as identical securities. '''

        return (self.asset == other.asset and self.mode == other.mode and 
                self.date == other.date and 
                self.strike_price == other.strike_price)

    def combine(self, other):
        ''' Combine the other Option into this one, keeping the price of this
            one. '''

        if self.asset != other.asset:
            raise Exception(f"Assets do not match: {self.asset} vs {other.asset}")
        if self.mode != other.mode:
            raise Exception(f"Modes do not match: {self.mode} vs {other.mode}")
        if self.date != other.date:
            raise Exception(f"Dates do not match: {self.date} vs {other.date}")
        if self.strike_price != other.strike_price:
            raise Exception(f"Strikes do not match: {self.strike_price} vs {other.strike_price}")

        self.buy_cost += other.buy_cost
        self.n_contracts += other.n_contracts

    def compute_needed_funding(self, min_target_price):
        ''' Compute how much total funding is needed.
        
            Returns a list of integer monetary values, one for each 
            upgrade target, indicating how much money is needed between
            the previous target and this one.
        '''

        # TODO: Sort upgrade targets by asset sell price.

        already_accounted_for = 0
        upgrade_targets = []
        tiered_needs = []
        for upgrade_target in self.upgrade_targets:
            if upgrade_target.asset_sell_price < min_target_price:
                continue

            upgrade_target.fixup_price()
            sell_value = upgrade_target.option_sell_price.unit_value * self.n_contracts * 100
            this_needed = self.buy_cost.unit_value - sell_value - already_accounted_for
            
            upgrade_targets.append(upgrade_target)
            tiered_needs.append(this_needed)
            already_accounted_for += this_needed
        
        return upgrade_targets, tiered_needs

    def __repr__(self):
        return f"Option[id={self.option_id},date={self.date},mode={self.mode},strikePrice={self.strike_price},nContracts={self.n_contracts},price={self.price}]"


class OptionUpgradeTarget:
    def __init__(self, asset_sell_price, option_sell_price, currency_kind='USD'):
        ''' Target for upgrading a PUT Option (or part of a PUT Option). This
            contains information useful for the option stage.
        
            PUT options lose value as the underlying asset price increases. We
            can buy shares of the underlying asset that will increase in value
            to compensate for the PUT option's loss in value.
        '''

        self.currency_kind = currency_kind
        self.asset_sell_price = fixup_price(asset_sell_price, currency_kind)
        self.option_sell_price = fixup_price(option_sell_price, currency_kind)

    def fixup_price(self):
        self.asset_sell_price = fixup_price(self.asset_sell_price, self.currency_kind)
        self.option_sell_price = fixup_price(self.option_sell_price, self.currency_kind)

    def to_dict(self, context: SerializeContext):
        return {
            "currencyKind": self.currency_kind,
            "assetSellPrice": self.asset_sell_price,
            "optionSellPrice": self.option_sell_price
        }

    def __repr__(self) -> str:
        return f"OptionUpgradeTarget[assetPrice:{self.asset_sell_price:.2f}, optionPrice:{self.option_sell_price:.2f}]"


def option_from_dict(data_dict):
    return Option(data_dict)
