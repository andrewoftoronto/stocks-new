from decimal import Decimal
from bisect import bisect_left
from util import penny_round


class OptionPricing:
    def __init__(self, data_points):
        self.data_points = data_points

        self.tables, self.valid_strikes = rebuild_structures(data_points)

    def find(self, mode: str, date: str, strike: int, asset_price: Decimal):
        ''' Find price of an option with the given asset price. 
        
            This will interpolate among data for the same mode, date and strike.
        '''

        key = make_key(mode, date, strike)
        table = self.tables[key]

        i = bisect_left(table, asset_price, key=lambda x: x[0])
        if i == 0:
            (_, option_price) = table[0]
        elif i == len(table):
            (_, option_price) = table[i - 1]
        else:
            upper_asset_price, upper_option_price = table[i]
            lower_asset_price, lower_option_price = table[i - 1]
            
            asset_price_diff = float(upper_asset_price - lower_asset_price)
            option_price_diff = float(upper_option_price - lower_option_price)
            interp = float(asset_price - lower_asset_price) / asset_price_diff
            option_price = lower_option_price + Decimal(option_price_diff * interp)
        
        return penny_round(option_price)
        
    def lower_strike(self, mode: str, date: str, asset_price: Decimal):
        ''' Determine the highest strike price lower than the given asset price
            for which this has data. 
        '''

        strike_data = self.valid_strikes[make_strike_key(mode, date)]
        i = bisect_left(strike_data, asset_price)
        if i == 0:
            raise Exception("No lower strike found")
        else:
            return strike_data[i - 1]

    def update_price(self, option, asset_price):
        option.price = self.find(option.mode, option.date, option.strike_price,
                asset_price)


def rebuild_structures(data_points):

    tables = {}
    strikes = {}
    for p in data_points:
        mode = p[0]
        date = p[1]
        strike = p[2]
        asset_price = p[3]
        option_price = p[4]

        key = make_key(mode, date, strike)
    
        if key in tables:
            table = tables[key]
        else:
            table = []
            tables[key] = table
        table.append((Decimal(asset_price), Decimal(option_price)))

        strike_key = make_strike_key(mode, date)
        if strike_key in strikes:
            strike_data = strikes[strike_key]
        else:
            strike_data = []
            strikes[strike_key] = strike_data
        strike_data.append(Decimal(strike))

    for (_, v) in tables.items():
        v.sort(key=lambda x: x[0])

    for (_, v) in strikes.items():
        v.sort()

    return tables, strikes

def make_key(mode : str, date : str, strike : int) -> str:
    key = date + " " + str(strike) + " " + mode
    return key

def make_strike_key(mode : str, date : str) -> str:
    key = date + " " + mode
    return key