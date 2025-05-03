from decimal import Decimal
from serialize_context import SerializeContext
from util import to_dict


class UpgradeTarget:
    def __init__(self, asset_sell_price: Decimal, option_sell_price: Decimal):
        ''' Target for upgrading a PUT Option (or part of a PUT Option). This
            contains information useful for the option stage.
        
            PUT options lose value as the underlying asset price increases. We
            can buy shares of the underlying asset that will increase in value
            to compensate for the PUT option's loss in value.
        '''

        self.asset_sell_price = Decimal(asset_sell_price)
        self.option_sell_price = Decimal(option_sell_price)

    def to_dict(self, context: SerializeContext):
        return {
            "assetSellPrice": self.asset_sell_price,
            "optionSellPrice": self.option_sell_price
        }

    def __repr__(self) -> str:
        return f"UpgradeTarget[assetPrice:{self.asset_sell_price:.2f}, optionPrice:{self.option_sell_price:.2f}]"


class Option:
    ''' Corresponds to an option '''

    def __init__(self, asset, mode, date, strike_price, n_contracts, price, 
            buy_cost=None, theta=Decimal(0), upgrade_funding=Decimal(0),
            upgrade_targets: UpgradeTarget=[]):
        self.asset = asset
        self.mode = mode
        self.date = date
        self.strike_price = strike_price
        self.n_contracts = n_contracts
        self.price = Decimal(price)
        self.upgrade_funding = upgrade_funding
        self.upgrade_targets = upgrade_targets

        if theta is not None:
            self.theta = Decimal(theta)
        else:
            self.theta = Decimal(0)

        if buy_cost is None:
            buy_cost = Decimal(price * n_contracts * 100)
        self.buy_cost = buy_cost

    def __repr__(self):
        price = self.get_price()
        value = price * self.n_contracts * 100
        return f"{self.n_contracts} {self.date} ${self.strike_price:.2f} {self.mode}: ${price:.2f} x {self.n_contracts} x 100 = ${value:.2f}; [cost: ${self.buy_cost:.2f}; theta: ${self.theta:.4f}]"

    def name(self) -> str:
        return f"{self.n_contracts} x {self.date} ${self.strike_price:.2f} {self.mode}"

    def get_price(self):
        return self.price

    def value(self):
        price = self.get_price()
        return Decimal(price * self.n_contracts * 100)

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

    def transform(self, n_contracts, new_mode, new_date, new_strike, new_price,
            new_theta=Decimal(0)):
        ''' Sell n_contracts of current Option and buy n_contracts of a 
            related Option.
         
            Make sure to set the price of this Option to whatever you sold the
            options for before calling this.

            This will modify the current Option and provide a new Option, 
            reflecting the operations.  

            Similar to ACB tax calculation, if there is a loss from selling the 
            original option, it will be added to the cost of the new option.
            This is done under the assumption that gains can be added to
            another account, such as the borrow fund while losses are more
            likely to just be withheld. This will not affect the return value.

            Returns (Option, Decimal): The transformed option and the net
            profit or loss from selling the original option.
        '''
        
        new_price = Decimal(new_price)

        if n_contracts <= 0:
            raise Exception(f"Invalid number of contracts: {n_contracts}")
        if n_contracts > self.n_contracts:
            raise Exception(f"Attempted to transform more contracts than exist: {n_contracts} > {self.n_contracts}")

        # Adjust buy cost based on cost being taken away by the contracts that 
        # are being sold.
        lost_cost = self.buy_cost / self.n_contracts * n_contracts
        self.buy_cost = self.buy_cost - lost_cost

        self.n_contracts -= n_contracts

        # Use upgrade funding to cover losses.
        sell_profit = _compute_sell_profit(self, n_contracts, lost_cost)
        
        buy_cost = new_price * n_contracts * 100
        new_option = Option(self.asset, new_mode, new_date, new_strike,
                n_contracts, new_price, buy_cost, theta=new_theta)
        return new_option, sell_profit

    def sell(self, n_contracts, new_price=None):
        ''' Sell n contracts, modifying the option in place.

            Returns the net profit or loss.
        '''

        if new_price is not None:
            self.price = Decimal(new_price)

        # Adjust buy cost based on cost being taken away by the contracts that 
        # are being sold.
        lost_cost = self.buy_cost / self.n_contracts * n_contracts
        self.buy_cost = self.buy_cost - lost_cost

        self.n_contracts -= n_contracts

        sell_profit = _compute_sell_profit(self, n_contracts, lost_cost)

        return sell_profit

    def add_overridden_profit(self, profit: Decimal):
        ''' Options can be set as override profit destinations in assets. If so,
            this adds the profit to the upgrade funding. '''

        self.upgrade_funding += profit

    def get_serialize_id(self, context: SerializeContext):
        return context.new_str_id(self, "o")

    def to_dict(self, context: SerializeContext):
        upgrade_targets = None if self.upgrade_targets is None else to_dict(self.upgrade_targets, context)
        return {
            "mode": self.mode,
            "date": self.date,
            "strikePrice": self.strike_price,
            "nContracts": self.n_contracts,
            "price": self.price,
            "buyCost": self.buy_cost,
            "theta": self.theta,
            "id": self.get_serialize_id(context),
            "upgradeFunding": self.upgrade_funding,
            "upgradeTargets": upgrade_targets
        }

def new_option_from_dict(d, ctx: SerializeContext) -> Option:
    ''' Construct an option from the given dictionary. '''

    upgrade_targets = []
    if d["upgradeTargets"] is not None:
        upgrade_targets_dict = d["upgradeTargets"]
        upgrade_targets = [UpgradeTarget(
            asset_sell_price=Decimal(u["assetSellPrice"]), 
            option_sell_price=Decimal(u["optionSellPrice"])
        ) for u in upgrade_targets_dict]

    o = Option(asset=ctx.asset, mode=d["mode"], date=d["date"],
            strike_price=d["strikePrice"], n_contracts=d["nContracts"], 
            price=Decimal(d["price"]), buy_cost=Decimal(d["buyCost"]),
            theta=Decimal(d["theta"]), upgrade_funding=Decimal(d["upgradeFunding"]),
            upgrade_targets=upgrade_targets)
    ctx.id_to_value[d["id"]] = o
    return o


def _compute_sell_profit(option, n_contracts, lost_cost):
    ''' Attempt to use option's upgrade funding to cover a loss where
        n_contracts is the number of contracts sold and lost_cost is total
        buy cost of the contracts sold.
    
        Assumes:
        - option.price is the sell price, 
        - option.n_contracts is the number of contracts left after selling
    '''

    sell_profit = option.price * 100 * n_contracts - lost_cost 
    if option.n_contracts == 0:

        # Realize any upgrade_cost as profit when option is fully closed out.
        sell_profit += option.upgrade_funding
        option.upgrade_funding = Decimal(0)
    elif sell_profit < 0:

        # Try to cover loss using upgrade_funding.
        take = min(option.upgrade_funding, -sell_profit)
        sell_profit += take
        option.upgrade_funding -= take

    return sell_profit
