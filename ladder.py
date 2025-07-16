from decimal import Decimal
import pytz
import datetime
from util import to_dict, penny_round, decimal_get
from stage import StageBase
from serialize_context import SerializeContext
from target import Target, new_target_from_dict


class RungDef:
    ''' Template that defines how to generate a ladder rung. '''

    def __init__(self, sell_times: Decimal, profit: Decimal,
            min_share_profit_ratio: Decimal, min_profit: Decimal = None,
            disable_trend_threshold: Decimal = None,
            disable_days = None):
        
        # Maximum number of times from the current price that the sell price of
        # the rung will be. If exceeded, the rung's price will be lowered.
        self.sell_times = Decimal(sell_times)

        # Initial amount of profit to make off this rung when the target is 
        # reached.
        # As the rung lowers, the target profit is gradually reduced to 
        # min_profit. This helps save on the costs needed to buy more shares to
        # satisfy the target as the rung lowers.
        self.profit = Decimal(profit)

        # Minimum amount of profit per-share that the rung's target allows.
        # This will affect the rung target's max_buy_price. 
        self.min_share_profit_ratio = Decimal(min_share_profit_ratio)

        # Minimum profit that the rung's target can make.
        if min_profit is None:
            self.min_profit = Decimal(profit)
        else:
            self.min_profit = Decimal(min_profit)

        # If the price decreases by this amount without increasing in between,
        # then this rung will be disabled.
        self.disable_trend_threshold = disable_trend_threshold

        # Ladder rungs are disabled on these days.
        self.disable_days = disable_days

    def to_dict(self, context: SerializeContext):
        return {
            "id": context.new_id(self),
            "sellTimes": self.sell_times,
            "profit": self.profit,
            "minProfit": self.min_profit,
            "minShareProfitRatio": self.min_share_profit_ratio,
            "disableTrendThreshold": self.disable_trend_threshold,
            "disableDays": self.disable_days
        }
    
    def __repr__(self):
        return (f"RungDef[sellTimes: {self.sell_times:.3f}, "
            f"profit: {self.profit:.2f}, " +
            f"minProfit: {self.min_profit:.2f}, " +
            f"minShareProfitRatio: {self.min_share_profit_ratio:.2f}, " + 
            f"disableTrendThreshold: {self.disable_trend_threshold}], " +
            f"disableDays: {self.disable_days}")


class Rung:
    ''' A rung in the Ladder. '''

    def __init__(self, definition: RungDef, target: Target, 
            start_price: Decimal, disabled: bool):
        self.definition = definition
        self.target = target
        self.start_price = start_price
        self.lowest_price = start_price
        self.disabled = disabled

    def apply_decay_fn(self, decay_fn):
        self.start_price = decay_fn(self.start_price)
        self.lowest_price = decay_fn(self.lowest_price)
        self.target.apply_decay_fn(decay_fn)

    def to_dict(self, context: SerializeContext):
        return {
            "definitionID": context.value_to_id[self.definition],
            "target": self.target.to_dict(context),
            "startPrice": self.start_price,
            "lowestPrice": self.lowest_price,
            "disabled": self.disabled
        }
    
    def __repr__(self):
        return (f"Rung[target: {self.target}, " +
            f"disabled: {self.disabled}, " +
            f"startPrice: {self.start_price:.2f}, " +
            f"lowestPrice: {self.lowest_price:.2f}]")


class Ladder(StageBase):
    '''  A moving Ladder that ensures that targets are always within reach
        even as the price drops. 
        
        Ladders use a series of rungs to generate targets. Each rung is
        associated with a rate of return, R, such that between the time that the
        target was first created to when the target was reached, the price had
        made a transition from 1x to Rx.

        Rungs are placed at regular logarithmic intervals, such as 1.02x,
        1.0404x, etc.

        In addition, as the price goes down, the last rung can be repeated so
        that even as the price lowers, the target horizon remains at the same
        price, with new rungs generated to fill the space in between.
        '''
    
    def __init__(self, defs, def_to_rungs, rung_frequency, min_trend_point=None,
                max_trend_point=None, paused=False):
        self.rung_defs = defs
        self.def_to_rungs = def_to_rungs
        self.horizon = None
        self.rung_frequency = Decimal(rung_frequency)
        self.min_trend_point = min_trend_point
        self.max_trend_point = max_trend_point
        self.paused = paused

    def on_update(self, current_price: Decimal, min_margin: Decimal):
        ''' Updates the ladder. '''

        if not isinstance(current_price, Decimal):
            current_price = Decimal(current_price)

        # Update trend tracking.
        if self.min_trend_point is None or self.max_trend_point is None:
            self.min_trend_point = current_price
            self.max_trend_point = current_price

        else:

            # On each update, the trend either continues or is reset.
            # A trend reset happens when current_price is a certain threshold
            # higher than min_trend_point.
            if self.min_trend_point * Decimal(1.015) < current_price:
                self.min_trend_point = current_price
                self.max_trend_point = current_price
            else:
                self.min_trend_point = min(self.min_trend_point, current_price)
                self.max_trend_point = max(self.max_trend_point, current_price)

            # In a strong downward trend, disable rung defs that have reached
            # their threshold.
            # Also disable based on week-days if set.
            for (rung_def, rungs) in self.def_to_rungs.items():
                if rung_def.disable_days is not None:
                    timezone = pytz.timezone("America/Toronto")
                    now = datetime.datetime.now(timezone)
                    day = now.weekday()
                    if day in rung_def.disable_days:
                        for rung in rungs:
                            if not rung.disabled:
                                rung.disabled = True
                                print(f"Day of week disabling rung: {rung}")


                if rung_def.disable_trend_threshold is not None:
                    ratio = Decimal((self.max_trend_point - current_price) / self.max_trend_point)
                    if rung_def.disable_trend_threshold <= ratio:
                        for rung in rungs:
                            if not rung.disabled:
                                rung.disabled = True
                                print(f"Downward trend disabling rung: {rung}")

        # Remove rungs that have been reached.
        new_def_to_rungs = {}
        for (rung_def, rungs) in self.def_to_rungs.items():
            fn = lambda r: current_price < r.target.sell_price
            remaining_rungs = list(filter(fn, rungs))
            if 0 < len(remaining_rungs):
                new_def_to_rungs[rung_def] = remaining_rungs
        self.def_to_rungs = new_def_to_rungs

        if self.paused:
            return

        # Set horizon point so that we can fill up to that point with rungs.
        proposed_horizon = penny_round(current_price * self.rung_defs[-1].sell_times)
        if self.horizon is not None:
            self.horizon = max(proposed_horizon, self.horizon)
        else:    
            self.horizon = proposed_horizon

        # Create ordered points to help in the following algorithm.
        ordered_points = []
        for (i, rung_def) in enumerate(self.rung_defs):
            rungs = self.def_to_rungs.get(rung_def, None)
            if rungs is not None:
                ordered_points += [(i, rung.target.sell_price) for rung in rungs]
        ordered_points = sorted(ordered_points, key=lambda p: (p[0], p[1]))

        # Create rungs if there's room for them and adjust existing rungs so
        # that they satisfy the constraint that they are no more than sell 
        # times above current price.
        # We will handle adjusting the horizon separately.
        for (number, rung_def) in enumerate(self.rung_defs):

            # Enforce rung disable rules.
            if rung_def.disable_days is not None:
                timezone = pytz.timezone("America/Toronto")
                now = datetime.datetime.now(timezone)
                day = now.weekday()
                if day in rung_def.disable_days:
                    continue

            rungs = self.def_to_rungs.get(rung_def, [None])
            for (i, rung) in enumerate(rungs):
                max_sell_price = penny_round(current_price * 
                        rung_def.sell_times * self.rung_frequency ** i)

                # Threshold where any rung with price lower than this prevents
                # creating a new rung from this rung_def if it didn't exist already.
                new_threshold = max_sell_price + (current_price * 
                        self.rung_frequency - current_price) * Decimal(0.25)

                if rung is None:

                    # See if conditions are right to create the rung.
                    can_create = True
                    for price_point in ordered_points:
                        other_number = price_point[0]
                        other_price = price_point[1]
                        if (number <= other_number and other_price < new_threshold):
                            can_create = False
                            break

                    if can_create:

                        # The update pass below will override some of these values.
                        rung = create_rung(rung_def, max_sell_price, 
                                current_price, False)
                        self.def_to_rungs[rung_def] = [rung]
                else:

                    # Rung exists already, update it's price.
                    target = rung.target
                    target.sell_price = min(target.sell_price, max_sell_price)
            
        # Fill up to the horizon. We include some tolerance to smooth out
        # horizon spawning.
        # A target is only supposed to be marked as is_horizon if it was
        # created on the edge of the horizon as the share price goes up, rather
        # than when space opens up as the share price goes down.
        last_def = self.rung_defs[-1]
        last_rungs = self.def_to_rungs[last_def]
        last_price = last_rungs[-1].target.sell_price
        while last_price * self.rung_frequency + Decimal(0.02) < self.horizon:
            price = penny_round(last_price * self.rung_frequency)
            last_price = price

            # Detect horizon edge using simple heuristic.
            is_horizon = current_price * last_def.sell_times >= price

            last_rungs.append(create_rung(last_def, price, current_price,
                    is_horizon))

        # Update all rungs.
        for (rung_def, rungs) in self.def_to_rungs.items():
            for (i, rung) in enumerate(rungs):
                target = rung.target
                sell_price = target.sell_price

                sell_times = rung_def.sell_times * self.rung_frequency ** i
                rung.lowest_price = min(rung.lowest_price, current_price)
                rung.target.profit = adjust_target_profit(rung_def.profit, 
                        rung_def.min_profit, rung.start_price, rung.lowest_price,
                        sell_times, min_margin=min_margin)
                target.max_buy_price = penny_round(sell_price / 
                        rung_def.min_share_profit_ratio)
                target.min_buy_price = min(target.min_buy_price, Decimal(float(current_price) * 0.99))

        pass

    def generate_targets(self):
        ''' Generates targets from the rungs of the ladder. '''
        
        targets = []
        for (_, rungs) in self.def_to_rungs.items():
            targets += [r.target for r in rungs if not r.disabled]
        return targets

    def on_horizon_filled(self, id):
        ''' Receive message from asset telling that a target that requested 
            from the horizon fund received the requested shares. '''
        for rungs in self.def_to_rungs.values():
            for rung in rungs:
                if rung.target.horizon_request_id == id:
                    rung.target.horizon_request_id = None

    def get_stage_kind(self) -> str:
        return "ladder"
    
    def get_highest_ready_price(self) -> Decimal:
        ''' Gets the highest supported price where any rungs on the horizon
            will already be paid up to that point. '''

        return penny_round(self.horizon / self.rung_defs[-1].sell_times)

    def enable_rungs(self, reset_price):
        ''' Enable all disabled rungs and clear the trend. '''

        self.min_trend_point = reset_price
        self.max_trend_point = reset_price
        for (_, rungs) in self.def_to_rungs.items():
            for rung in rungs:
                rung.disabled = False

    def scale_profit_levels(self, scale_factor:float, min_margin:Decimal):
        ''' Scale profit levels of rung targets according to scale factor. '''

        for rung_def in self.rung_defs:
            rung_def.profit = penny_round(Decimal(float(rung_def.profit) * scale_factor))
            rung_def.min_profit = penny_round(Decimal(float(rung_def.min_profit) * scale_factor)) 

        for (rung_def, rungs) in self.def_to_rungs.items():
            for (i, rung) in enumerate(rungs):
                sell_times = rung_def.sell_times * self.rung_frequency ** i
                rung.target.profit = adjust_target_profit(rung_def.profit, 
                    rung_def.min_profit, rung.start_price, rung.lowest_price,
                    sell_times, min_margin=min_margin)

    def reset_profit_levels(self, reset_price: Decimal):
        ''' Reset the profit levels of rung targets. '''

        for (_, rungs) in self.def_to_rungs.items():
            for rung in rungs:
                rung.start_price = min(rung.start_price, reset_price)

    def apply_decay_fn(self, function):
        ''' Apply the given decay factor n times. '''

        if self.horizon is not None:
            self.horizon = function(self.horizon)

        for (_, rungs) in self.def_to_rungs.items():
            for rung in rungs:
                rung.apply_decay_fn(function)

    def tax_profits(self, profit: Decimal) -> Decimal:
        ''' Unused '''
        return profit

    def to_dict(self, context: SerializeContext):
        d_defs = to_dict(self.rung_defs, context)

        d_rungs = {}
        for (rung_def, rungs) in self.def_to_rungs.items():
            def_id = context.value_to_id[rung_def]
            d_rungs[def_id] = to_dict(rungs, context)

        return {
            "stage_kind": self.get_stage_kind(),
            "defs": d_defs,
            "rungs": d_rungs,
            "rungFrequency": self.rung_frequency,
            "horizon": self.horizon,
            "minTrendPoint": self.min_trend_point,
            "maxTrendPoint": self.max_trend_point,
            "paused": self.paused
        }
    
    def __repr__(self):
        return (f"Ladder[rungDefs: {self.rung_defs}, " +
            f"minTrendPoint: {self.min_trend_point}, " +
            f"maxTrendPoint: {self.max_trend_point}, " +
            f"defToRungs: {self.def_to_rungs}]")
    

def create_rung(rung_def: RungDef, sell_price: Decimal, 
        current_price: Decimal, is_horizon: bool) -> Rung:
    ''' Create ladder rung that sells at the indicated price level. '''

    from uuid import uuid4

    name = f"{rung_def.sell_times:.3f}x"

    horizon_request_id = uuid4() if is_horizon else None
    target = Target(name, rung_def.profit, sell_price, 
        current_price, current_price, horizon_request_id=horizon_request_id     
    )
    return Rung(rung_def, target=target, start_price=current_price, disabled=False)


def new_rung_def_from_dict(d, context: SerializeContext) -> RungDef:

    rung_def = RungDef(
        sell_times=Decimal(d["sellTimes"]),
        profit=Decimal(d["profit"]),
        min_share_profit_ratio=Decimal(d["minShareProfitRatio"]),
        min_profit=Decimal(d["minProfit"]),
        disable_trend_threshold=decimal_get(d, "disableTrendThreshold", None),
        disable_days=d.get("disableDays", None),
    )
    context.id_to_value[d["id"]] = rung_def
    return rung_def


def new_rung_from_dict(d, context: SerializeContext) -> Rung:
    target = new_target_from_dict(d["target"], context)
    start_price = Decimal(d["startPrice"])
    disabled = d.get("disabled", False)
    r = Rung(definition=context.id_to_value[d["definitionID"]],
        target=target, start_price=start_price, disabled=disabled)
    r.target = new_target_from_dict(d["target"], context)
    r.start_price = Decimal(d["startPrice"])
    r.lowest_price = Decimal(d["lowestPrice"])
    return r


def new_ladder_from_dict(d, context: SerializeContext) -> Ladder:

    # Serialize rung defs first.
    defs = [new_rung_def_from_dict(def_dict, context) for def_dict in d["defs"]]

    # De-serialize rungs
    def_to_rungs = {}
    for (def_id, rungs_dict) in d["rungs"].items():
        definition = context.id_to_value[int(def_id)]
        def_to_rungs[definition] = []
        if not isinstance(rungs_dict, list):
            raise Exception("Failed to read rungs")
        for rung_dict in rungs_dict:
            rung = new_rung_from_dict(rung_dict, context)
            def_to_rungs[definition].append(rung)
    ladder = Ladder(defs, def_to_rungs, d["rungFrequency"])
    ladder.horizon = Decimal(d["horizon"])
    ladder.max_trend_point = decimal_get(d, "maxTrendPoint", None)
    ladder.min_trend_point = decimal_get(d, "minTrendPoint", None)
    ladder.paused = bool(d["paused"])
    return ladder


def adjust_target_profit(max_profit: Decimal, min_profit: Decimal, 
        start_price: Decimal, lowest_price: Decimal, 
        sell_times: Decimal, min_margin: Decimal) -> Decimal:
    ''' Adjust profit of a rung target based on how the lowest price reached
        since the target was created. The adjustment essentially assumes that
        the target was initially satisfied with shares bought at "start_price".
        It considers how much profit that those shares bought at "start_price" 
        would make when the target was moved and the asset price became 
        "lowest_price". 

        This calculation uses simplifications like ignoring things like 
        min-margin profit on the original buy.
    '''

    # Calculate how many shares at "start_price" were needed to satisfy the
    # target.
    original_sell_price = start_price * sell_times
    buy_price = min(start_price, original_sell_price / min_margin)
    original_per_share_profit = original_sell_price - buy_price
    n_at_start = max_profit / original_per_share_profit

    lowest_sell_price = lowest_price * sell_times
    lowest_per_share_profit = lowest_sell_price - buy_price
    lowest_profit = penny_round(lowest_per_share_profit * n_at_start)

    adjusted_profit = min(max(lowest_profit, min_profit), max_profit)
    return adjusted_profit


if __name__ == '__main__':
    first_def = RungDef(1.01 ** 2, Decimal(50), 1.005, min_profit=30)
    second_def = RungDef(1.01 ** 3, Decimal(50), 1.01 ** 2, min_profit=30)
    ladder = Ladder([first_def, second_def], {}, 1.01)

    ladder.on_update(70)
    ladder.on_update(69.5)

    context = SerializeContext()
    d = ladder.to_dict(context)
    ladder_reconstructed = new_ladder_from_dict(d, context)
    print(ladder_reconstructed)