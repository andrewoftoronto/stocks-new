from shares import Shares, new_shares_from_dict
from target import Target
from serialize_context import SerializeContext

class Assignment:
    ''' Assignment of shares to a target. '''

    def __init__(self, target: Target, shares: Shares, profit: int):
        self.target = target
        self.shares = shares
        self.profit = profit


def new_assignment_from_dict(dict, context: SerializeContext) -> Assignment:
    ''' Creates a new assignment from the given dict. '''

    target = context.id_to_value[dict["targetID"]]
    shares = new_shares_from_dict(dict)
    profit = context.id_to_value["profit"]
    return Assignment(target, shares, profit)