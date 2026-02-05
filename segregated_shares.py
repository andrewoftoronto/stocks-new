from typing import List
from shares import BaseShares, Shares, new_shares_from_dict, new_empty_shares
from serialize_context import SerializeContext


class SegregatedShares(BaseShares):
    ''' Collection of shares that can be partitioned into different groups or
        taken as a whole.

        The first group will generally be considered the default group that
        receives any added shares.
    '''

    def __init__(self, groups: List[Shares]):
        self.groups = groups

    def total_buy_cost(self):
        ''' Compute total money paid to own all current shares. '''
        value = 0
        for group in self.groups:
            value += group.total_buy_cost()
        return value

    def to_pairs(self, clone=True) -> Shares:
        ''' Gets all shares in this collection. 
        
            Note that clone flag is ignored because the returned data will
            always be unshared.
        '''

        shares = Shares()
        for group in self.groups:
            shares += group

        return shares
    
    def to_dict(self, context: SerializeContext):
        ''' Converts this to a dictionary for serialization. '''

        return [group.to_dict(context) for group in self.groups]
    
    def __len__(self) -> int:
        ''' Gets the number of shares in this. '''

        n_shares = 0
        for group in self.groups:
            n_shares += len(group)
        return n_shares
    
    def __repr__(self) -> str:
        return str(self.groups)
    
    def __getitem__(self, index):
        ''' Get the indicated group. '''

        return self.groups[index]
    
    def __setitem__(self, index, new_group):
        ''' Set the indicated group. '''

        self.groups[index] = new_group


def new_segregated_shares_from_dict(dict, default_n_groups) -> SegregatedShares:
    ''' Creates a SegregatedShares from the given dictionary. '''

    if dict is None:
        return new_empty_segregated_shares(default_n_groups)

    groups = [new_shares_from_dict(g) for g in dict]
    return SegregatedShares(groups)

def new_empty_segregated_shares(nGroups: int, currency_kind: str='USD') -> SegregatedShares:
    ''' Creates a SegregatedShares containing just the default group. '''

    groups = [new_empty_shares(currency_kind) for i in range(0, nGroups)]
    return SegregatedShares(groups)
