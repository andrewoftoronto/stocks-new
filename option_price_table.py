from option_estimate import binomial_tree_american_option
from decimal import Decimal


class OptionPriceTable:
    ''' Table listing out prices of Options under different 
        (strike, underlying) price conditions. 
    '''

    def __init__(self):
        self.call_strike_underlying_to_price = {}
        self.put_strike_underlying_to_price = {}

    def contains_call(self, strike, underlying):
        if strike not in self.call_strike_underlying_to_price:
            return False
        return underlying in self.call_strike_underlying_to_price[strike]

    def contains_put(self, strike, underlying):
        if strike not in self.put_strike_underlying_to_price:
            return False
        return underlying in self.put_strike_underlying_to_price[strike]

    def set_call(self, strike, underlying, price):
        set(self.call_strike_underlying_to_price, strike, underlying, price)

    def set_put(self, strike, underlying, price):
        set(self.put_strike_underlying_to_price, strike, underlying, price)

    def get_call(self, strike, underlying):
        if not self.contains_call(strike, underlying):
            raise Exception(f"Missing CALL s=${strike} @ ${underlying}")

        return Decimal(self.call_strike_underlying_to_price[strike][underlying])

    def get_put(self, strike, underlying):
        if not self.contains_put(strike, underlying):
            raise Exception(f"Missing PUT s=${strike} @ ${underlying}")

        return Decimal(self.put_strike_underlying_to_price[strike][underlying])

    def get(self, mode, strike, underlying):
        if mode == 'PUT':
            return self.get_put(strike, underlying)
        elif mode == 'CALL':
            return self.get_call(strike, underlying)
        else:
            raise Exception("Invalid mode for get", mode)


class BSMPriceTable:
    def __init__(self):
        self.cache = OptionPriceTable()

    def get_call(self, strike, underlying):
        if self.cache.contains_call(strike, underlying):
            return self.cache.get_call(strike, underlying) 

        T = 216 / 365
        r = 0.0434
        sigma = 0.5
        N = 216
        price = binomial_tree_american_option(underlying, strike, T, r, sigma, 
                N, option_type='call')
        self.cache.set_call(strike, underlying, price)
        return price

    def get_put(self, strike, underlying):
        if self.cache.contains_put(strike, underlying):
            return self.cache.get_put(strike, underlying) 

        T = 216 / 365
        r = 0.0434
        sigma = 0.5
        N = 216
        price = binomial_tree_american_option(underlying, strike, T, r, sigma, 
                N, option_type='put')
        self.cache.set_put(strike, underlying, price)
        return price
    
    def get(self, mode, strike, underlying):
        if mode == 'PUT':
            return self.get_put(strike, underlying)
        elif mode == 'CALL':
            return self.get_call(strike, underlying)
        else:
            raise Exception("Invalid mode for get", mode)


def set(structure, strike, underlying, value):
    if strike not in structure:
        structure[strike] = {underlying: value}
    else:
        structure[strike][underlying] = value