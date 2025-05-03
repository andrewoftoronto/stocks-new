from decimal import Decimal
from stage import StageBase
from serialize_context import SerializeContext
from target import Target, new_target_from_dict
from util import to_dict

class Custom(StageBase):
    '''  A stage where targets can be manually created. '''
    pass

    def __init__(self, targets=None):
        if targets is None:
            self.targets = []
        else:
            self.targets = targets

    def get_stage_kind(self) -> str:
        return "custom"
    
    def new_target(self, sell_price: Decimal, name: str, profit: Decimal, 
            max_buy_price: Decimal, min_buy_price: Decimal):
        ''' Adds a new target to this.
        '''

        target = Target(name, profit, sell_price, max_buy_price, min_buy_price)
        self.targets.append(target)

    def on_update(self, current_price: Decimal, min_margin: Decimal):
        self.targets = list(filter(lambda x: x.sell_price > current_price, 
                self.targets))
        for target in self.targets:
            target.min_buy_price = min(target.min_buy_price, current_price)
        pass

    def generate_targets(self):
        return self.targets

    def to_dict(self, context: SerializeContext):
        target_dict = to_dict(self.targets, context)
        return {
            "stage_kind": "custom",
            "targets": target_dict
        }

    def on_horizon_filled(self, _):
        ''' For compatibility with this function on things like Ladders. '''
        pass

    def apply_decay_fn(self, decay_fn):
        ''' Apply the given decay function. '''

        for target in self.targets:
            target.apply_decay_fn(decay_fn)

    def tax_profits(self, profit: Decimal) -> Decimal:
        ''' Unused '''
        return profit

    def get_highest_ready_price(self) -> Decimal:
        ''' For compatibility with this function on things like Ladders. 
        
            Custom targets don't move or get spontaneously created, so this is
            just set to a very big number.
        '''

        return Decimal(9999999)

    def scale_profit_levels(self, scale: float, min_margin: Decimal):
        ''' For compatibility with this function on things like ladders.
        '''

        pass


    def reset_profit_levels(self, reset_price: Decimal):
        ''' For compatibility with this function on things like ladders.

            Custom targets don't get their profits automatically adjusted, so
            this just does nothing. 
        '''

        pass

    def enable_rungs(self, reset_price: Decimal):
        ''' For compatibility with this function on things like ladders.'''

        pass


def new_custom_from_dict(d, context: SerializeContext) -> Custom:
    targets = []
    for dict_target in d["targets"]:
        target = new_target_from_dict(dict_target, context)
        targets.append(target)
    return Custom(targets)