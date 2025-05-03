from decimal import Decimal
from option_price_table import OptionPriceTable
from serialize_context import SerializeContext


class OptionHistoryItem:
    def __init__(self, description, value):
        self.description = description
        self.value = value

    def __repr__(self):
        return f"{self.description}; delta$: {self.value:.2f}"
    
    def to_dict(self):
        return {"description": self.description, "value": self.value}


class OptionChain:
    ''' Track a chain of PUT and CALL options used for borrowing. '''

    def __init__(self, asset, mode, strike_price, price, n_borrows, n_contracts, active=False, history=None):
        self.asset = asset
        self.mode = mode
        self.strike_price = strike_price
        self.price = price
        self.n_borrows = n_borrows
        self.n_contracts = n_contracts
        self.active = active

        if history is not None:
            self.history = history
        else:
            price = self.get_price()
            self.history = [new_buy_event(mode, asset.price, strike_price, price, n_contracts)]

    def __repr__(self):
        price = self.get_price()
        cost = price * self.n_contracts * 100

        active_str = "[INACTIVE]" if not self.active else ""
        return f"{active_str} {self.n_contracts} ${self.strike_price:.2f} {self.mode}: ${price:.2f} x {self.n_contracts} x 100 = ${cost:.2f}"

    def value(self):
        price = self.get_price()
        return Decimal(price * self.n_contracts * 100)

    def lifetime_value(self):
        total = Decimal(0.0)
        for item in self.history:
            total += Decimal(item.value)

        if self.active:
            total += self.value()

        return total

    def get_price(self) -> Decimal:
        if isinstance(self.price, OptionPriceTable):
            return self.price.get(self.mode, self.strike_price, self.asset.price)
        else:
            return self.price

    def set_price(self, price) -> Decimal:
        ''' Sets the price and returns it, correctly handling the case where
            self.price is OptionPriceTable and price is None.
        
            If self.price is OptionPriceTable and price is None, this will just
            return what the price should be.
        '''

        if price is None:
            if not isinstance(self.price, OptionPriceTable):
                raise Exception("Unable to deduce option price.")
            price = self.price.get(self.mode, self.strike_price, self.asset.price)
            return price
        else:
            self.price = price
            return price

    def on_buy(self, price=None):
        ''' Call when buying the option. This will make the option active. '''

        if self.active:
            raise Exception("OptionChain already marked as active.")
        
        if price is None:
            if not isinstance(self.price, OptionPriceTable):
                raise Exception("Unable to deduce option price.")
            price = self.price.get(self.mode, self.strike_price, self.asset.price)
        else:
            self.price = price

        self.history.append(new_buy_event(self.mode, self.asset.price, self.strike_price, price, self.n_contracts))
        self.active = True

    def on_sell(self, price=None):
        ''' Call when selling the option. This will mark the option as inactive. 
        '''

        if not self.active:
            raise Exception("OptionChain already marked as inactive.")
        
        if price is None:
            if not isinstance(self.price, OptionPriceTable):
                raise Exception("Unable to deduce option price.")
            price = self.price.get(self.mode, self.strike_price, self.asset.price)
        else:
            self.price = price

        self.history.append(new_sell_event(self.mode, self.asset.price, self.strike_price, price, self.n_contracts))
        self.active = False

    def on_transform(self, new_mode, new_strike_price, old_price=None, new_price=None):
        ''' Call when transforming this option into a new form. This is 
            equivalent to selling in its current form and buying in the new 
            form. 
            
            Returns the change in cash balance that would happen as a result of
            the transformation.
            '''

        old_mode = self.mode
        old_strike_price = self.strike_price
        old_price = self.set_price(old_price)
        old_value = self.value()

        self.mode = new_mode
        self.strike_price = new_strike_price
        new_price = self.set_price(new_price)
        new_value = self.value()

        self.history.append(new_transfer_event(self.asset.price, old_mode, 
            old_strike_price, old_price, new_mode, new_strike_price, 
            new_price, self.n_contracts))

        return old_value - new_value

    def on_borrow(self, new_strike_price, old_price=None, new_price=None):

        old_strike_price = self.strike_price
        old_price = self.set_price(old_price)
        old_value = self.value()

        new_mode = 'CALL'
        self.mode = new_mode
        self.strike_price = new_strike_price
        new_price = self.set_price(new_price)
        new_value = self.value()

        self.history.append(new_borrow_event(self.asset.price,
            old_strike_price, old_price, new_strike_price, 
            new_price, self.n_borrows, self.n_contracts))

        return old_value - new_value
    
    def on_unborrow(self, new_strike_price, old_price=None, new_price=None):

        old_strike_price = self.strike_price
        old_price = self.set_price(old_price)
        old_value = self.value()

        new_mode = 'PUT'
        self.mode = new_mode
        self.strike_price = new_strike_price
        new_price = self.set_price(new_price)
        new_value = self.value()

        self.history.append(new_unborrow_event(self.asset.price, 
            old_strike_price, old_price, new_strike_price, 
            new_price, self.n_borrows, self.n_contracts))

        return old_value - new_value

    def to_dict(self, context: SerializeContext):
        return {
            "mode": self.mode,
            "strike": self.strike_price,
            "price": self.price,
            "nBorrows": self.n_borrows,
            "nContracts": self.n_contracts,
            "active": self.active,
            "history": [event.to_dict() for event in self.history]   
        }


def new_buy_event(mode, underlying, strike_price, price, n_contracts):
    cost = price * n_contracts * 100
    return OptionHistoryItem(f"[${underlying:.2f}] BUY {n_contracts} ${strike_price:.2f} {mode} delta$: ${price:.2f} x {n_contracts} x 100", -cost)


def new_sell_event(mode, underlying, strike_price, price, n_contracts):
    cost = price * n_contracts * 100
    return OptionHistoryItem(f"[${underlying:.2f}] SELL {n_contracts} ${strike_price:.2f} {mode}; delta$: ${price:.2f} x {n_contracts} x 100", cost)


def new_transfer_event(underlying, old_mode, old_strike, old_price, mode, 
        strike_price, new_price, n_contracts):
    old_label = f"{n_contracts} ${old_strike:.2f} {old_mode} (${old_price})"
    new_label = f"{n_contracts} ${strike_price:.2f} {mode} (${new_price})"
    old_cost = old_price * n_contracts * 100
    new_cost = new_price * n_contracts * 100
    net_change = old_cost - new_cost
    return OptionHistoryItem(f"[${underlying:.2f}] TRANSFER {old_label} -> {new_label}", net_change)


def new_borrow_event(underlying, old_strike, old_price,
        strike_price, new_price, n_borrows, n_contracts):
    old_label = f"{n_contracts} ${old_strike:.2f} PUT (${old_price:.2f})"
    new_label = f"{n_contracts} ${strike_price:.2f} CALL (${new_price:.2f})"
    old_cost = old_price * n_contracts * 100
    new_cost = new_price * n_contracts * 100
    net_change = old_cost - new_cost + underlying * n_borrows
    return OptionHistoryItem(f"[${underlying:.2f}] BORROW {n_borrows} shares; {old_label} -> {new_label}", net_change)


def new_unborrow_event(underlying, old_strike, old_price,
        strike_price, new_price, n_borrows, n_contracts):
    old_label = f"{n_contracts} ${old_strike:.2f} CALL (${old_price:.2f})"
    new_label = f"{n_contracts} ${strike_price:.2f} PUT (${new_price:.2f})"
    old_cost = old_price * n_contracts * 100
    new_cost = new_price * n_contracts * 100
    net_change = old_cost - new_cost - underlying * n_borrows
    return OptionHistoryItem(f"[${underlying:.2f}] UNBORROW {n_borrows} shares; {old_label} -> {new_label}", net_change)


def new_option_from_dict(dict, asset, context: SerializeContext) -> OptionChain:
    ''' Creates a new asset from the given dictionary. '''

    mode = dict['mode']
    strike = dict['strike']
    price = Decimal(dict['price'])
    n_borrows = dict["nBorrows"]
    n_contracts = dict['nContracts']
    active = dict['active']
    history = [OptionHistoryItem(event["description"], event["value"]) for event in dict['history']]
    o = OptionChain(asset, mode, strike, price, n_borrows, n_contracts, active, history)
    return o