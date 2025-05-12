from decimal import Decimal
from stage import StageBase
from serialize_context import SerializeContext
from target import Target, new_target_from_dict
from util import to_dict
from option import Option
from math import ceil


# Penalty to apply to the estimated sell price of an option due to certain
# factors:
# - Getting ripped off by bid-ask spread.
# - Reduction in volatility
# The estimate for the price that an option can actually be sold will be
# reduced by this ratio. For example, if the option is estimated to be worth 
# $10, with a penalty of 0.05 = 5%, then we assume we'll actually sell it at 
# $9.5.
SELL_PENALTY = 0.05

# Rate at which to tax incoming profits to fund future option upgrades.
UPGRADE_TAX_RATE = 0.1


class OptionTarget:
    ''' Tracks an option and its corresponding target. '''

    def __init__(self, option: Option, targets=[], profit_level=None):
        self.option = option
        self.targets = targets

        # Total profit being targeted, including any upgrade funding so far. The 
        # algorithm is conservative about downsizing the total profit level and
        # tries to allocate extra room initially so that it can avoid needing 
        # to resize frequently.
        self.profit_level = profit_level

    def to_dict(self, context: SerializeContext):
        return {
            "optionID": self.option.get_serialize_id(context),
            "targets": to_dict(self.targets, context),
            "profitLevel": self.profit_level
        }


class OptionStage(StageBase):
    '''  A stage where targets can be manually created. '''
    pass

    def __init__(self, asset=None, o_targets=None):
        self.asset = asset
        if o_targets is None:
            self.o_targets = []
        else:
            self.o_targets = o_targets

    def get_stage_kind(self) -> str:
        return "option"

    def __repr__(self) -> str:
        targetReports = []
        for t in self.o_targets:
            if 0 < len(t.option.upgrade_targets):
                upgrade_target = t.option.upgrade_targets[0]
                report = f"{t.option.name()}; {upgrade_target}; {t.option.upgrade_funding:.2f}/${t.profit_level:.2f}"
            else:
                report = f"{t.option.name()}; {t.option.upgrade_funding:.2f}/${t.profit_level:.2f}"
        targetReports.append(report)

        targetReports = ','.join(targetReports)
        return f"OptionStage[targets:[{targetReports}]]"

    def on_option_sold(self, option: Option):
        ''' Call when an option has been fully sold off. '''

        if option.n_contracts > 0:
            return
        
        o_target = None
        for iter_o_target in self.o_targets:
            if iter_o_target.option == option:
                o_target = iter_o_target

        if o_target is None:
            return
        
        self.o_targets.remove(o_target)


    def on_update(self, current_price: Decimal, min_margin: Decimal):

        # Match existing targets with options.
        new_targets = []
        for option in self.asset.options:

            # Remove upgrade targets that have been reached.
            upgrade_target = None
            while len(option.upgrade_targets) > 0:
                upgrade_target = option.upgrade_targets[0]
                if current_price < upgrade_target.asset_sell_price:
                    break
                else:
                    option.upgrade_targets = option.upgrade_targets[1:]
                    upgrade_target = None
            upgrade_asset_sell_price = upgrade_target.asset_sell_price if upgrade_target is not None else Decimal(1000)
            upgrade_option_sell_price = upgrade_target.option_sell_price if upgrade_target is not None else Decimal(1000)

            # Match against targets
            matching_target = None
            for o_target in self.o_targets:
                if o_target.option == option:
                    matching_target = o_target
                    break
            
            if matching_target is None:
                matching_target = OptionTarget(option, [])
            new_targets.append(matching_target)

            # Remove targets that exceed the option-target sell-price.
            matching_target.targets = list([target for target in matching_target.targets if target.sell_price <= upgrade_asset_sell_price])

            # Remove targets that have been reached and have any profit 
            # redirected into the option's upgrade fund.
            reached_targets = list([target for target in matching_target.targets if target.sell_price <= current_price])
            for target in reached_targets:
                if target.sell_price <= current_price:
                    self.asset.add_profit_dest_override(matching_target.option, target.profit)

            matching_target.targets = list([target for target in matching_target.targets if current_price < target.sell_price])

            # Update min buy price and compute amount of money already
            # accounted for in targets.
            already_accounted = Decimal(0)
            for target in matching_target.targets:
                target.min_buy_price = min(target.min_buy_price, current_price)
                already_accounted += Decimal(target.profit)

            # Compute how much profit is needed to satisfy the option-target.
            est_opt_sell_price = Decimal(float(upgrade_option_sell_price) * (1 - SELL_PENALTY))
            needed_profit_level = max(0, option.buy_cost - est_opt_sell_price * option.n_contracts * 100)

            # Profit level builds in a generous margin to avoid frequent resizing.
            if matching_target.profit_level is None or matching_target.profit_level + 10 < needed_profit_level:
                matching_target.profit_level = Decimal(ceil(float(needed_profit_level) / 50) * 50 + 200)

            needed = matching_target.profit_level - already_accounted - matching_target.option.upgrade_funding
            if upgrade_target is not None and needed > 10:
                name = "option-upgrade"
                sell_price = upgrade_asset_sell_price
                max_buy_price = Decimal(float(current_price) * 1.02)
                target = Target(name, needed, sell_price, max_buy_price, current_price)
                matching_target.targets.append(target)

        self.o_targets = new_targets

    def tax_profits(self, profit: Decimal) -> Decimal:
        ''' Potentially withhold some profit to help pay upgrade fees. '''
        
        # Identify option-targets that need funding.
        targets_needing_funding = []
        for option_target in self.o_targets:

            # Skip for options that were fully sold but this hasn't updated to
            # reflect yet.
            if option_target.option.n_contracts == 0:
                continue

            needed = option_target.profit_level - option_target.option.upgrade_funding
            if 0 < needed:
                targets_needing_funding.append((option_target, needed))

        if len(targets_needing_funding) == 0:
            return profit

        # We tax profits at most for UPGRADE_TAX_RATE. With n targets, each 
        # target is entitled to at most an equal share of that: 
        #     share = profit * UPGRADE_TAX_RATE / n
        # For simplicity, if a target needs less than share, we won't try to 
        # redistribute that to other targets.
        share_per_target = Decimal(float(profit) * UPGRADE_TAX_RATE / len(targets_needing_funding))
        profit_remaining = profit
        for (option_target, needed) in targets_needing_funding:
            to_take = min(share_per_target, needed)
            profit_remaining -= to_take
            option_target.option.upgrade_funding += to_take

        total_tax_paid = profit - profit_remaining
        if profit_remaining < profit:
            print(f"Option-Stage took ${total_tax_paid:.2f} in taxes.")
        return profit_remaining

    def generate_targets(self):
        targets = []
        for o_target in self.o_targets:
            targets += o_target.targets
        return targets
    
    def on_horizon_filled(self, _):
        ''' For compatibility with this function on things like Ladders. '''
        pass

    def apply_decay_fn(self, decay_fn):
        ''' For compatibility. Targets are not decayed like in custom or 
            ladder stages. '''
        pass

    def to_dict(self, context: SerializeContext):
        target_dict = to_dict(self.o_targets, context)
        return {
            "stage_kind": "option",
            "oTargets": target_dict
        }

    def get_highest_ready_price(self) -> Decimal:
        ''' For compatibility with this function on things like Ladders.
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


def new_option_stage_from_dict(d, context: SerializeContext) -> OptionStage:
    o_targets = []
    for o_target_dict in d["oTargets"]:
        option = context.id_to_value[o_target_dict["optionID"]]

        dict_targets = o_target_dict["targets"]
        targets = []
        for target_dict in dict_targets:
            targets.append(new_target_from_dict(target_dict, context))

        profit_level = o_target_dict["profitLevel"]
        profit_level = None if profit_level is None else Decimal(profit_level)

        target = OptionTarget(option, targets, profit_level)
        o_targets.append(target)

    return OptionStage(context.asset, o_targets)