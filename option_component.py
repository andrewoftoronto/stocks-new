from math import ceil
from copy import copy
from currency import Currency
from target import load_target, Target
from asset import BOUND_SHARES


class OptionComponent:
    ''' Asset component that provides additional features and support for 
        options and option upgrade tracking. '''

    def __init__(self, p, asset, data_dict=None):
        self.p = p
        self.asset = asset
        self.option_to_targets = load_option_to_targets(data_dict)

    def update(self):

        # Evaluate option upgrade funding, creating new targets if needed.
        for option in self.asset.options:
            
            # Collect existing sell-targets that may already be providing some
            # funding for this option.
            if option in self.option_to_targets:
                existing_targets = option_to_targets[option]
            else:
                existing_targets = []
                self.option_to_targets[option] = existing_targets
            existing_targets = copy(existing_targets)

            # Match sell-targets to the lowest upgrade target above them.
            # carryover_funding: tracks funding already promised and new
            #   funding and tracks the excess funding beyond what was
            #   needed that is carried over to the next upgrade target.
            #   Initially, for the first target, we simply include the
            #   existing option upgrade funding.
            max_utarget_price = self.asset.price * 1.05
            upgrade_targets, tiered_needs = option.compute_needed_funding(max_utarget_price)
            carryover_funding = option.upgrade_funding.unit_value
            print(carryover_funding, tiered_needs)
            for upgrade_target, needed in zip(upgrade_targets, tiered_needs):
                
                # Collect existing relevant sell-targets.
                to_remove = []
                for target in existing_targets:
                    carryover_funding += target.profit.unit_value
                    to_remove.append(target)
                existing_targets = [t for t in existing_targets if t not in to_remove]

                # Create new sell-target to cover needed funding.
                if carryover_funding < needed:
                    print(f"Funding needed: {carryover_funding} vs {needed}")

                    # Round profit in new targets to this. Note multiplication
                    # for cents.
                    target_rounding = 50 * 100

                    sell_price = upgrade_target.asset_sell_price.unit_value
                    print("Sell price", sell_price)
                    profit = ceil((needed - carryover_funding) / target_rounding) * target_rounding
                    max_buy_price = int(round(self.asset.price.unit_value * 1.03))
                    min_buy_price = int(round(self.asset.price.unit_value / 1.05))
                    target = Target({
                        'sellPrice': Currency(sell_price, self.asset.currency_kind),
                        'profit': Currency(profit, self.asset.currency_kind),
                        'maxBuyPrice': Currency(max_buy_price, self.asset.currency_kind),
                        'minBuyPrice': Currency(min_buy_price, self.asset.currency_kind),
                    })
                    self.option_to_targets[option].append(target)
                    print(f"Creating target: {sell_price} for {profit}")

                # Subtract needed to compute funding to be carried over to the
                # next upgrade target.
                carryover_funding -= needed

        # TODO: Clean out old non-existant options from option_to_targets.

    def sell_target(self, target):
        self.asset.fixup_price()

        # Find option that this target is attached to.
        option = None
        targets_list = None
        for consider_option, consider_targets in self.option_to_targets.items():
            for consider_target in consider_targets:
                if target == consider_target:
                    option = consider_option
                    targets_list = consider_targets
        if option is None:
            raise Exception("Option related to target to sell not found")

        shares = self.asset.get_target_assignment(target).clone()

        # Ignore shares more expensive than the asset price.
        shares = shares.as_split([self.asset.price])[0]

        self.asset.shares[BOUND_SHARES] -= shares
        profit = shares.compute_profit(self.asset.price, min_buy_price=0, 
            min_margin=1.0)
        option.upgrade_funding += profit

        # Detach the target from the data structure.
        targets_list.remove(target)

    def sell_targets(self, option):
        self.asset.fixup_price()

        targets_list = self.option_to_targets[option]
        for target in targets_list:
            shares = self.asset.get_target_assignment(target).clone()

            # Ignore shares more expensive than the asset price.
            shares = shares.as_split([self.asset.price])[0]

            self.asset.shares[BOUND_SHARES] -= shares
            profit = shares.compute_profit(self.asset.price, min_buy_price=0, 
                min_margin=1.0)
            option.upgrade_funding += profit

        # Detach the target from the data structure.
        targets_list.clear()

    def get_targets(self):
        targets = []
        for option_sell_targets in self.option_to_targets.values():
            targets += option_sell_targets
        return targets


def load_option_component(p, asset, data_dict):
    return OptionComponent(p, asset, data_dict)


def load_option_to_targets(data_dict):
    if data_dict is None:
        return {}

    option_to_targets = {}
    for option_id, targets_dict in data_dict['oTargets'].items():
        option = self.asset.get_option_by_id(option_id)
        targets = [load_target(target_dict) for target_dict in targets_dict]
        option_to_targets[option] = targets
