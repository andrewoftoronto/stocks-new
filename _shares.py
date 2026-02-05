from math import ceil
from decimal import Decimal
from typing import List
from copy import deepcopy
import util
import sys
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
        is.
    '''

    def __init__(self, pairs=None, no_convert=False):
        if pairs is not None:
            self.pairs = pairs if no_convert else convert_to_pairs(pairs)
        else:
            self.pairs = []

    def value(self, price: int) -> int:
        ''' Gets the total value of all Shares at the given price. '''
        return price * len(self)

    def total_buy_cost(self) -> int:
        ''' Gets the total amount of money paid to purchase all current shares. '''
        total_value = 0
        for pair in self.pairs:
            total_value += pair[0] * pair[1]
        return total_value

    def to_dict(self, context: SerializeContext):
        ''' Converts this Shares into a dictionary for serialization. '''
        return self.pairs
    
    def sort(self):
        ''' Fixup the sorted-ness of this Shares. '''
        sort_pairs(self.pairs)

    def to_pairs(self, clone=True):
        ''' Converts this Shares into raw pairs and optionally clones them. '''
        if clone:
            return deepcopy(self.pairs)
        else:
            return self.pairs

    def top(self, n) -> Self:
        ''' Gets the top n shares. '''

        extracted_pairs = first_shares(reversed(self.pairs), n)
        return Shares(extracted_pairs)
    
    def slice(self, n_start, n_end) -> Self:
        ''' Slice shares based on lowest to highest cost. This will return
            (n_end - n_start) shares. '''
        
        lowest = self.bottom(n_start)
        return (self - lowest).bottom(n_end - n_start)

    def bottom(self, n) -> Self:
        ''' Gets the bottom n shares. '''

        extracted_pairs = first_shares(self.pairs, n)
        return Shares(extracted_pairs)

    def as_split(self, price_levels) -> List[Self]:
        ''' Splits individual shares into different Shares based on price 
        levels. '''
        if len(price_levels) == 0:
            return [self.clone()]

        split_points = sorted(price_levels)
        groups = []

        current_group = Shares()
        current_upper = split_points[0]
        split_points = split_points[1:]
        for pair in self.pairs:

            while current_upper is not None and pair[0] > current_upper:
                current_upper = split_points[0] if len(split_points) > 0 else None
                split_points = split_points[1:]
                groups.append(current_group)
                current_group = Shares()

            current_group.pairs.append([pair[0], pair[1]])

        groups.append(current_group)
        if len(groups) < len(price_levels) + 1:
            n_missing_groups = len(price_levels) + 1 - len(groups)
            groups += [Shares() for i in range(0, n_missing_groups)]

        return groups

    def set(self, other):
        ''' Assigns the given shares to this in-place. other will be cloned.
        '''
        self.pairs = convert_to_pairs(other)

    def change(self, price, quantity):
        ''' Change the quantity of shares at the indicated price level.
        '''
        if quantity < 0:
            raise Exception("Quantity to set is negative.")

        pair = get_pair(self.pairs, price)
        if pair is not None:
            if quantity != 0:
                pair[1] = quantity
            else:
                self.pairs.remove(pair)
        elif quantity != 0:
            self.set(self + [price, quantity])

    def make_mean(self) -> Self:
        ''' Create a new Shares based on this one where every share has the 
            same price - the mean of this one's. This conserves purchase cost. 
        '''

        cost = self.total_purchase_value()
        n = len(self)
        price = util.penny_round(cost / n, fn=ceil)
        return Shares([price, n])

    def take(self) -> Self:
        ''' Removes all shares from this and returns them. '''
        pairs = self.pairs
        self.pairs = []
        return Shares(pairs)

    def shift_prices(self, d_price: Decimal):
        ''' Shifts the prices of all shares by the given delta. '''

        for pair in self.pairs:
            pair[0] += Decimal(d_price)
        self.sort()

    def scale_prices(self, f_price: Decimal):
        ''' Scales the prices of all shares by the given factor. '''

        for pair in self.pairs:
            pair[0] *= Decimal(f_price)
        self.sort()

    def scale_quantities(self, f_qty: float):
        ''' Scales the number of shares by the given factor. Note that 
            reverse-splits can cause rounding errors. '''

        for pair in self.pairs:
            pair[1]  = int(round(pair[1] * f_qty))
        self.sort()

    def distribute_value(self, amount: Decimal):
        ''' Distribute value evenly to the shares. '''

        per_share = Decimal(amount) / n_shares
        n_shares = len(self)
        for pair in self.pairs:
            pair[0] += per_share

    def clone(self) -> Self:
        ''' Clones this Shares. '''
        return Shares(deepcopy(self.pairs), no_convert=True)

    def validate(self):
        for pair in self.pairs:
            if pair[1] == 0:
                raise Exception(f"Contains pair with 0 shares: {pair}")

    def __len__(self) -> int:
        ''' Gets the number of shares in this. '''
        n_shares = 0
        for pairs in self.pairs:
            n_shares += pairs[1]
        return n_shares
    
    def __str__(self) -> str:
        text = "["
        for (i, pair) in enumerate(self.pairs):
            text += f"${pair[0]:.2f} x {int(pair[1])}"
            if i < len(self.pairs) - 1:
                text += ", "
    
        text += "]"
        return text
        
    def __repr__(self) -> str:
        return self.__str__()

    def __add__(self, other_in) -> Self:
        ''' Adds the given other shares to this to create a new Shares. '''

        result = self.clone()
        other_pairs = convert_to_pairs(other_in)
        merge_pairs(result.pairs, other_pairs)
        return result
    
    def __sub__(self, other_in) -> Self:
        ''' Returns a new Shares that is the result of removing all shares from
            other. This will return an exception if this is missing any share
            found in other.
        '''

        result = self.clone()
        other_pairs = convert_to_pairs(other_in)

        for pair in other_pairs:
            existing_pair = get_pair(result.pairs, pair[0])
            if existing_pair is None:
                raise Exception(f"Missing price being removed: {pair[0]}")
            if existing_pair[1] < pair[1]:
                raise Exception(f"Insufficient shares: {existing_pair[1]} - {pair[1]}")
            
            existing_pair[1] -= pair[1]

        prune_zeros(result.pairs)
        return result
    
    def top_profit(self, profit: Decimal, sell_price: Decimal, 
            min_buy_price: Decimal, 
            min_margin: Decimal=Decimal(1.0)) -> tuple[Self, Decimal]:
        ''' Starting from the most expensive shares, get the minimum set of shares
            needed to fund the given profit goal. 
            
            Returns (Shares, profit).    
        '''
        
        pairs_remaining = self.pairs[:]
        extracted_pairs = []
        accum_profit = 0
        while len(pairs_remaining) > 0:
            if profit <= accum_profit:
                break

            pair = pairs_remaining.pop(-1)
            n_to_take, pair_profit = pair_n_needed_for_profit(pair, 
                profit - accum_profit, sell_price, min_buy_price, min_margin)
            accum_profit += pair_profit
            extracted_pairs.append([pair[0], n_to_take])

        return Shares(extracted_pairs), accum_profit

    def compute_profit(self, sell_price: Decimal, min_buy_price=Decimal(0.0), 
            min_margin: Decimal=Decimal(1.0)) -> Decimal:
        ''' Computes the profit from selling these shares at the given price.
        '''
        accum_profit = 0
        for pair in self.pairs:
            adjusted_buy_price = min(pair[0], sell_price / min_margin)
            profit_per_share = sell_price - max(adjusted_buy_price, min_buy_price)
            accum_profit += profit_per_share * pair[1]
        return accum_profit


def remove_pair(pairs, price):
    ''' Remove the indicated share pair from the given pairs. '''

    pair = get_pair(pairs, price)
    if pair is None:
        raise Exception(f"Attempt to remove non-existent pair @ ${price}")
    pairs.remove(pair)


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


def new_shares_from_dict(dict):
    ''' Loads a Shares object from the given dict. '''

    raw_pairs = dict
    pairs = []
    for pair in raw_pairs:
        price = pair[0]
        qty = pair[1]
        pairs.append([price, qty])
    return Shares(pairs)


def convert_to_pairs(in_stuff):
    ''' Convert the given input into raw share pairs and clones them. '''

    def assert_int(i) -> int:
        if not isinstance(i, int):
            raise Exception(f"{i} is not int")
        return i
    
    def fixup_pair(p):
        if p[1] <= 0:
            raise Exception(f"Pair contains 0/negative shares: {(p[0], p[1])}")
        return [Decimal(util.penny_round(p[0])), assert_int(p[1])]

    fixup_list = lambda li: [fixup_pair(p) for p in li if p[1] > 0]

    if isinstance(in_stuff, BaseShares):
        return in_stuff.to_pairs(clone=True)
    elif isinstance(in_stuff, list):
        if len(in_stuff) == 0:
            return []
        elif isinstance(in_stuff[0], Shares):
            raise Exception("Given list containing Shares object")
        elif isinstance(in_stuff[0], list) or isinstance(in_stuff[0], tuple):
            return fixup_list(in_stuff)
        else:

            # This is a single pair. We check to prevent creating a Shares()
            # that contains a negative or 0 quantity.
            if in_stuff[1] > 0:
                return [fixup_pair(in_stuff)]
            else:
                return []
    elif isinstance(in_stuff, tuple):
        return [deepcopy(fixup_pair(in_stuff))] 
    else:
        raise Exception("Unknown shares format.")
    

def sort_pairs(pairs):
    ''' Sorts the given pairs. 
      
        Pairs canonically should be sorted, so this can restore that property
        after an operation temporarily breaks it. In-place.
    '''

    pairs.sort(key=lambda p: p[0])


def prune_zeros(pairs):
    ''' Prunes out pairs that have zero shares. In-place. '''
    
    def f(p) -> bool:
        if p[1] < 0:
            raise Exception(f"Pair has negative quantity: {p[1]} @ ${p[0]}")
        return p[1] > 0

    pairs[:] = [p for p in pairs if f(p)]


def get_pair(pairs, price):
    ''' Extracts the given pair by price from the given set of pairs. '''

    for pair in pairs:
        if abs(pair[0] - price) < 0.005:
            return pair
    return None


def first_shares(pairs, n):
    ''' Extracts the n first shares from the given list of share pairs. The 
        results will be detached from the given list of pairs. '''

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

    sort_pairs(new_pairs)
    return new_pairs


def pair_n_needed_for_profit(pair, profit: Decimal, sell_price: Decimal, 
            min_buy_price: Decimal, 
            min_margin: Decimal = Decimal(1.0)) -> tuple[int, Decimal]:
    ''' Computes number of shares in a pair needed to obtain a certain profit
        level.

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
    
    adjusted_buy_price = min(pair[0], sell_price / min_margin)
    profit_per_share = sell_price - max(adjusted_buy_price, min_buy_price)
    n_sold_shares = min(int(ceil(profit / profit_per_share)), pair[1])
    return n_sold_shares, profit_per_share * n_sold_shares

    
