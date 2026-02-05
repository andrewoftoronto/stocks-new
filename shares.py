from math import ceil
from decimal import Decimal
from typing import List
from copy import deepcopy
import util
import sys
from currency import Currency, currency_from_common
from serialize_context import SerializeContext


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class BaseShares:
    ''' Base Shares interface. A class that extends this should provide basic
         Share manipulation and retrieval. 
    '''
    
    pass


class Shares(BaseShares):
    ''' Simple collection of shares of a particular asset.

        This does not use the Currency type to express prices. Instead the kind
        of currency is context-dependant; the user should already know what it 
        is. Share prices will be expressed as integers in the currency base
        unit.
    '''

    def __init__(self, data_dict):
        self.currency_kind = data_dict['currencyKind']

        if 'commonPairs' in data_dict:
            self.pairs = _common_to_raw(data_dict['commonPairs'], self.currency_kind)
        elif 'rawPairs' in data_dict:
            self.pairs = data_dict['rawPairs']
        else:
            raise Exception("Unknown share data format. Use either commonPairs or rawPairs.")

    def clone(self):
        return Shares({
            'currencyKind': self.currency_kind,
            'rawPairs': deepcopy(self.pairs)
        })

    def compute_profit(self, sell_price, min_buy_price=0, min_margin=1):
        ''' Compute the profit from selling shares.

            min_buy_price: minimum price that profit can be awarded at. If a
              share is cheaper, then it will be treated as though it cost this
              much. If in conflict, this overrides the effects of min_margin.
            min_margin: minimum profit margin per share, ensuring that even
              if a share cost more than a certain amount, it will be treated
              as if it yielded this min_margin ratio of profit.
        '''
        
        sell_price = util.fixup_price(sell_price, self.currency_kind).unit_value
        min_buy_price = util.fixup_price(min_buy_price, self.currency_kind).unit_value

        accum_profit = 0
        for pair in self.pairs:
            adjusted_buy_price = min(pair[0], int(round(sell_price / min_margin)))
            profit_per_share = sell_price - max(adjusted_buy_price, min_buy_price)
            accum_profit += profit_per_share * pair[1]
        return Currency(accum_profit, self.currency_kind)

    def as_split(self, price_levels) -> List[Self]:
        ''' Splits individual shares into different Shares based on price 
        levels. '''

        if len(price_levels) == 0:
            return [self.clone()]
        else:
            price_levels = [util.fixup_price(p, self.currency_kind).unit_value for p in price_levels]

        split_points = sorted(price_levels)
        groups = []

        current_group = new_empty_shares(self.currency_kind)
        current_upper = split_points[0]
        split_points = split_points[1:]
        for pair in self.pairs:

            while current_upper is not None and current_upper < pair[0]:
                current_upper = split_points[0] if len(split_points) > 0 else None
                split_points = split_points[1:]
                groups.append(current_group)
                current_group = Shares()

            current_group.pairs.append([pair[0], pair[1]])

        groups.append(current_group)
        
        # Add empty missing groups. The algorithm above will not have created
        # them since they don't have any shares.
        if len(groups) < len(price_levels) + 1:
            n_missing_groups = len(price_levels) + 1 - len(groups)
            groups += [new_empty_shares(self.currency_kind) for i in range(0, n_missing_groups)]

        return groups

    def bottom(self, n_shares):
        ''' Chose the n bottom shares. '''

        return _first_shares(self.pairs, n_shares)

    def __add__(self, other_in) -> Self:
        ''' Returns a new Shares that is the result of combining the shares
            from this and other_in together.
        '''

        result = self.clone()
        merge_pairs(result.pairs, _convert_to_pairs(other_in))
        return result

    def __sub__(self, other_in) -> Self:
        ''' Returns a new Shares that is the result of removing all shares
            that are also in other_in. This will return an exception if this 
            is missing any share found in other_in.
        '''

        result = self.clone()
        other_pairs = _convert_to_pairs(other_in)

        for pair in other_pairs:
            existing_pair = _get_pair(result.pairs, pair[0])
            if existing_pair is None:
                raise Exception(f"Missing price being removed: {pair[0]}")
            if existing_pair[1] < pair[1]:
                raise Exception(f"Insufficient shares: {existing_pair[1]} - {pair[1]}")
            
            existing_pair[1] -= pair[1]

        result.pairs = _prune_zeros(result.pairs)
        return result

    def __len__(self) -> int:
        n_shares = 0
        for pair in self.pairs:
            n_shares += pair[1]

        return n_shares


def new_empty_shares(currency_kind='USD'):
    return Shares({
        'currencyKind': currency_kind,
        'rawPairs': []
    })


def new_shares_from_dict(dict):
    ''' Loads a Shares object from the given dict. '''

    raise Exception("not implemented yet")


def new_shares_from_common(pairs, currency_kind='USD'):
    ''' Loads Shares from common decimal representation. '''

    return Shares({
        'currencyKind': currency_kind,
        'commonPairs': pairs
    })


def new_shares_from_raw(raw_pairs, currency_kind='USD'):
    ''' Loads Shares from raw representation. '''

    return Shares({
        'currencyKind': currency_kind,
        'rawPairs': raw_pairs
    })


def pair_n_needed_for_profit(pair, profit, sell_price, 
            min_buy_price, 
            min_margin = 1.0) -> tuple[int, int]:
    ''' Computes number of shares in a pair needed to obtain a certain profit
        level.

        All values should be in integer currency units - no decimals, floats, 
        Currency, etc.

        If this pair is incapable of satisfying the profit, then
        this will return the number of shares that maximizes profit as much as
        possible.

        min_margin pretends that shares above a certain buy price (but still
        below sell price) were bought cheaper so that they make a minimum 
        margin of profit. You can disable this by setting it to 1. This will
        report the profit with this adjustment.

        Returns (n_shares, profit).
    '''

    # If true, then it would not be profitable to sell.
    if sell_price <= pair[0]:
        return 0, 0
    
    adjusted_buy_price = min(pair[0], int(round(sell_price / min_margin)))
    profit_per_share = sell_price - max(adjusted_buy_price, min_buy_price)
    n_sold_shares = min(int(ceil(profit / profit_per_share)), pair[1])
    return n_sold_shares, profit_per_share * n_sold_shares


def sort_pairs(pairs):
    ''' Sorts the given pairs. 
      
        Pairs canonically should be sorted, so this can restore that property
        after an operation temporarily breaks it. In-place.
    '''

    pairs.sort(key=lambda p: p[0])


def merge_pairs(existing_pairs, new_pairs):
    ''' Merge new_pairs into existing_pairs in-place. Assumes that both inputs
        are correctly constructed pairs. '''

    for new_pair in new_pairs:

        found = False
        for existing_pair in existing_pairs:
            if new_pair[0] == existing_pair[0]:
                existing_pair[1] += new_pair[1]
                found = True
                break

        if not found:
            existing_pairs.append(new_pair)
    
    sort_pairs(existing_pairs)


def _common_to_raw(common_pairs, currency_kind):
    ''' Convert pairs with price in common float/decimal format (e.x. where 
        cents are represented using a decimal point) to the raw format
        that uses the smallest practical unit of currency.
    '''

    converted_pairs = []
    for (common_price, qty) in common_pairs:
        converted_price = currency_from_common(common_price, currency_kind).unit_value
        converted_pair = [converted_price, qty]
        converted_pairs.append(converted_pair)
    return converted_pairs
    

def _prune_zeros(pairs):
    ''' Return new share pair list based on pairs like [[price, qty], ...],
        such that it omits elements that have 0 qty. '''
    return [pair for pair in pairs if 0 < pair[1]]


def _convert_to_pairs(data):
    ''' Convert the given share data to raw pairs. '''

    if isinstance(data, Shares):
        return data.pairs
    else:
        return data


def _get_pair(pairs, price):
    ''' Extracts the given pair by price from the given set of pairs. '''

    for pair in pairs:
        if abs(pair[0] - price) < 0.005:
            return pair
    return None


def _first_shares(pairs, n):
    ''' Extracts the n first shares from the given list of share pairs.
    
        The given pairs don't necessarily need to be sorted in price order,
        but the results will be sorted in price order.
    '''

    remaining = n
    new_pairs = []
    for pair in pairs:
        if remaining == 0:
            break

        if remaining < pair[1]:
            new_pairs.append([pair[0], remaining])
            remaining = 0
            break
        else:
            new_pairs.append([pair[0], pair[1]])
            remaining -= pair[1]

    if remaining != 0:
        raise Exception(f"Not enough shares to extract all {n}; missing: {remaining}.")

    _sort_pairs(new_pairs)
    return new_pairs


def _sort_pairs(pairs):
    ''' Sorts the given pairs. 
      
        Pairs canonically should be sorted, so this can restore that property
        after an operation temporarily breaks it. In-place.
    '''

    pairs.sort(key=lambda p: p[0])