from copy import deepcopy
from decimal import Decimal
from math import ceil
from datetime import datetime
import pytz
from util import to_dict, penny_round, currency_collection_get
from typing import Optional
import fio
from shares import Shares, new_shares_from_dict
from segregated_shares import SegregatedShares, new_empty_segregated_shares, new_segregated_shares_from_dict
from target import Target, new_target_from_dict
from stages import new_stage_from_dict
from serialize_context import SerializeContext
from distribute import distribute, DistributionReport
from history import new_history_item_from_dict, HistoryItem
from option import Option, new_option_from_dict
from borrow_event import new_borrow_event_from_dict, BorrowEvent
from borrow_fund import income_tax_rate
from profit_dest_override import ProfitDestOverride, new_profit_dest_override_from_dict


# How many times higher in value the current price must be to be allowed to sell
# a share.
MIN_SELL_GAIN = Decimal(1.01)

# Index of segregated share account containing unbound shares.
UNBOUND_SHARES = 0

# Index of segregated share account containing bound shares.
BOUND_SHARES = 1

# Index of segregated share account containing shares reserved for expanding
# the horizon.
HORIZON_SHARES = 2

# Index of segregated share account containing shares reserved for manual
# use.
MANUAL_SHARES = 3


class Asset:
    ''' An asset that can be divided into shares with a particular price at 
        a point in time. '''

    def __init__(self, p, name=None, order=None, price=None, currency_kind=None,
            shares: Optional[SegregatedShares]=None, base_change = 0.0,
            margin_requirement = 0.0):
        self.p = p
        self.name = name
        self.order = order
        self.price = price
        self.currency_kind = currency_kind
        self.shares = shares or new_empty_segregated_shares(4)
        self.base_change = Decimal(base_change)

        self.surplus = Decimal(0)
        self.stages = []
        self.cached_targets = []
        self.cached_target_to_assignment = None

        self.borrow_events = []

        self.options = []

        self.history = []

        # Override where profits should go instead of just going to the general 
        # profit account.
        self.profit_dest_overrides = [] 

        self.daily_decay_factor = None

        self.recommended_sell = None
        self.recommended_buy = None

        self.option_pricing = None

        self.margin_requirement = margin_requirement

    def to_dict(self, context: SerializeContext):
        self.fixup_price()

        options = [to_dict(o, context) for o in self.options]
        return {
            "name": self.name,
            "order": self.order,
            "price": self.price,
            "currency": self.currency_kind,
            "shares": self.shares.to_dict(context),
            "surplus": self.surplus,
            "stages": to_dict(self.stages, context),
            "cachedTargets": to_dict(self.cached_targets, context),
            "borrowEvents": to_dict(self.borrow_events, context),
            "history": to_dict(self.history, context),
            "options": options,
            "dailyDecayFactor": self.daily_decay_factor,
            "baseChange": Decimal(self.base_change),
            "profitDestOverrides": to_dict(self.profit_dest_overrides, context),
            "marginRequirement": self.margin_requirement
        }

    def save(self, file_name: str):
        context = SerializeContext()
        fio.save(file_name, self.to_dict(context))

    def __repr__(self) -> str:

        n_shares = len(self.shares)
        n_physical_shares = self.n_physical_shares()

        option_value = Decimal(0)
        for option in self.options:
            option_value += option.value()

        money_value = Decimal(self.price * n_physical_shares) + option_value
        price = self.price
        eq = f"{n_physical_shares} ({n_shares}) {self.name} x ${price:.2f} + ${option_value:.2f} = ${money_value:.2f}"
        return f"{eq}; borrows: {self.n_borrowed()}; unbound: {len(self.shares[UNBOUND_SHARES])}; horizon: {len(self.shares[HORIZON_SHARES])}; manual: {len(self.shares[MANUAL_SHARES])}"

    def __len__(self) -> int:
        return len(self.shares)

    def n_physical_shares(self) -> int:
        return len(self.shares) - self.n_borrowed()

    def s(self, verbose=False) -> str:
        ''' Quick alias for summarize. '''
        self.summarize(verbose)

    def summarize(self, verbose=False) -> str:
        self.fixup_price()

        if self.cached_target_to_assignment is None:
            self.distribute()

        if verbose:
            log_targets = reversed(self.cached_targets)
        else:
            log_targets = []
            if len(self.cached_targets) > 0:
                log_targets.append(self.cached_targets[-1])
            if len(self.cached_targets) > 4:
                log_targets.append("...\n")
                log_targets += reversed(self.cached_targets[0:3])
            else:
                log_targets += reversed(self.cached_targets[0:len(self.cached_targets)-1])

        borrow_str = "["
        for (i, event) in enumerate(self.borrow_events):
            max_rebuy = event.get_max_rebuy()
            borrow_str += f"${max_rebuy:.2f} (${event.price:.2f}) x {event.n_shares} [${event.repay:.2f}/${event.funding:.2f}]"
            if i < len(self.borrow_events) - 1:
                borrow_str += ", "
        borrow_str += "]" 

        summary = ""
        for target in log_targets:
            log = write_target_log(target, self.cached_target_to_assignment)
            summary += f"{log}\n"
        summary += f"Unbound shares: {self.shares[UNBOUND_SHARES]}\n"
        summary += f"Horizon shares: {self.shares[HORIZON_SHARES]}\n"
        summary += f"Borrows: {borrow_str}\n"
        summary += str(self)

        print(summary)

    def distribute(self, all_shares=None) -> DistributionReport:
        ''' Distribute shares among the current targets. This recomputes which
            shares are bound versus unbound as well as creating the assignments
            of bound shares to targets. '''

        if all_shares is None:
            all_shares = self.shares[UNBOUND_SHARES] + self.shares[BOUND_SHARES]
        report = distribute(all_shares, self.cached_targets, self.price, 
                MIN_SELL_GAIN)
        self.shares[UNBOUND_SHARES] = report.unbound_shares
        self.shares[BOUND_SHARES] = all_shares - report.unbound_shares
        self.cached_target_to_assignment = report.target_to_assignment
        return report

    def update_strat(self):
        ''' Update strategy around this asset based on the current price. This
            will not buy or sell shares, just recommend some to buy or to sell. 
        '''

        self.fixup_price()

        # Make a checkpoint.
        self.p.checkpoint()

        self.distribute()

        # Identify the shares held by targets that will be sold. Later on, we
        # will hold these out so that they aren't considered for filling other 
        # targets.
        sold_shares = Shares()
        for target in self.cached_targets:
            if self.price < target.sell_price:
                break
            assignment = self.cached_target_to_assignment.get(target, None)
            if assignment is not None:
                sold_shares += assignment.shares

        # Update stages and generate targets from them.
        targets = []
        for stage in self.stages:
            stage.on_update(self.price, MIN_SELL_GAIN)
            targets += stage.generate_targets()
        targets = sorted(targets, key=lambda t: t.sell_price)
        self.cached_targets = targets

        # Try to fund horizon targets.
        horizon_targets = filter(lambda t: t.horizon_request_id is not None, targets)
        for target in horizon_targets:

            # Release as many shares from the horizon as it would take to
            # fund this target.
            eligible_shares = self.shares[HORIZON_SHARES].as_split([target.max_buy_price])[0]
            to_take, profit = eligible_shares.top_profit(target.profit, target.sell_price,
                    target.min_buy_price, MIN_SELL_GAIN)
            if profit < target.profit:
                print(f"Unable to fully fund target with horizon fund:\n  {target}.")

            self.shares[HORIZON_SHARES] -= to_take
            self.shares[UNBOUND_SHARES] += to_take

            for stage in self.stages:
                stage.on_horizon_filled(target.horizon_request_id)

        # Distribute shares and come up with recommendations. Shares that will
        # be sold for any targets reached are temporarily excluded during 
        # distribution but must be returned after.
        to_distribute = self.shares[UNBOUND_SHARES] + self.shares[BOUND_SHARES] - sold_shares
        report = self.distribute(to_distribute)
        self.shares[UNBOUND_SHARES] += sold_shares

        self.recommended_buy = None
        self.recommended_sell = None
        if report.buys_needed is not None and 0 < report.buys_needed:
            self.recommended_buy = report.buys_needed
            self.recommended_sell = sold_shares
        elif 0 < len(self.shares[UNBOUND_SHARES]):

            # Sell unbound shares sufficiently below price.
            unbound_to_sell = report.unbound_shares.as_split([self.price / MIN_SELL_GAIN])[0]
            self.recommended_sell = unbound_to_sell + sold_shares

        return self.recommended_sell, self.recommended_buy

    def horizon_urgency(self) -> float:
        ''' A score from 0->1 of how urgent it is to fill the horizon fund. '''

        # Urgency to fill up the horizon fund in any form at all.
        if len(self.shares[HORIZON_SHARES]) < 50:
            return 0.5

        horizon_price = ceil(float(self.price) * 1.02)
        n_already = len(self.shares[HORIZON_SHARES].as_split([horizon_price])[0])
        if n_already < 100: 

            week_day = datetime.now().weekday()
            if ((week_day == 2 and n_already < 25) or
                    (week_day == 3 and n_already < 50) or 
                    (week_day == 4 and n_already < 75)):
                urgency = 0.5
            else:
                urgency = 0.15
        else:
            urgency = 0

        return urgency

    def u(self, auto_sell=False):
        ''' Quick alias for update(). '''
        self.update(auto_sell)

    def update(self, auto_sell=False, hold_horizon=True):
        ''' Updates strategy and follows recommended actions. 

            It is possible for recommendations to include both buying and 
            selling. This will output a prompt for the user to indicate the
            net buy or net sell.

            With auto_sell=False, this will not do a net sell. It will at most
            cancel out any buys but leave the sell recommendation intact.
        '''

        self.fixup_price()

        if self.option_pricing is not None:
            for option in self.options:
                option.price = self.option_pricing.find(option.mode, option.date, option.strike_price, self.price)

        self.p.update()

        self.update_strat()

        # Try to fill the horizon fund with a fraction of shares being sold or
        # by buying extra.
        hold_ratio = self.horizon_urgency()
        n_horizon_buy = 0
        if hold_horizon and 0 < hold_ratio:

            if self.recommended_sell is not None and 0 < len(self.recommended_sell):
                n_withheld = int(ceil(len(self.recommended_sell) * hold_ratio))
                withheld = self.recommended_sell.top(n_withheld)
                self.shares[HORIZON_SHARES] += withheld
                self.shares[UNBOUND_SHARES] -= withheld
                self.recommended_sell -= withheld
            elif self.recommended_buy is not None and hold_ratio >= 0.5:
                n_horizon_buy = int(self.recommended_buy * hold_ratio)
                self.recommended_buy += n_horizon_buy

        n_sell = 0 if self.recommended_sell is None else len(self.recommended_sell)
        n_buy = 0 if self.recommended_buy is None else self.recommended_buy
        if not auto_sell:
            n_sell = min(n_sell, n_buy)

        if n_sell > 0:
            sold = self.sell(n_sell, do_checkpoint=False, prevent_oversell=True)
            self.recommended_sell -= sold
            print(f"Realized profit: ${sold.compute_profit(self.price):.2f}.")

            # If some shares have not made the minimum per-share profit, then
            # sell() may fail to sell them all.
            n_sell = len(sold)
        if n_buy > 0:
            self.recommended_buy -= n_buy
            self.buy(n_buy, do_checkpoint=False)
            self.unbound_to_horizon(n_horizon_buy)

        net_buy_sell = n_buy - n_sell
        d_money = net_buy_sell * self.price
        if net_buy_sell > 0:
            print(f"Bought {net_buy_sell} @ ${self.price:.2f} = ${d_money:.2f}.")
        elif net_buy_sell < 0:
            print(f"Sold {-net_buy_sell} @ ${self.price:.2f} = ${-d_money:.2f}.")
        else:
            print("No action taken")

        self.distribute()

    def buy(self, n=None, group:int=None, do_checkpoint: bool=True):
        ''' Buy n shares. If n is left None, this will buy the recommended
            number of shares from the last update action. '''

        self.fixup_price()
        if n is None:
            raise Exception("Not supported quite yet")
        
        if do_checkpoint:
            self.p.checkpoint()

        if group is None:
            group = UNBOUND_SHARES

        self.shares.groups[group] += Shares([self.price, n])
        self.p.account.currencies[self.currency_kind] -= self.price * n

        self.history.append(HistoryItem(datetime.now(), f"Bought {n}", len(self)))

    def sell(self, n: int=None, do_checkpoint: bool=True, prevent_oversell: bool=False):
        ''' Sell shares. 
        
            If n is not None: sells the n highest-priced unbound shares that 
                are sufficiently below their buy price.
            If n is None: sells the shares recommended by update to be sold.
        '''
        
        self.fixup_price()
        if n is None:
            raise Exception("Not supported quite yet.")

        # In computing to_sell: first gets all unbound shares below the minimum
        # allowed sell price; then takes the top n of those.
        unbound = self.shares.groups[UNBOUND_SHARES]
        sellable = unbound.as_split([self.price / MIN_SELL_GAIN])[0]
        n_actual_sell = n if not prevent_oversell else min(n, len(sellable))
        to_sell = sellable.top(n_actual_sell)

        if do_checkpoint:
            self.p.checkpoint()

        unbound.set(unbound - to_sell)
        self.p.account.currencies[self.currency_kind] += len(to_sell) * self.price

        # Distribute profit to any overrides first.
        remaining_profit = to_sell.compute_profit(self.price)
        while remaining_profit > 0 and len(self.profit_dest_overrides) > 0:
            o = self.profit_dest_overrides[0]

            take = min(o.value, remaining_profit)
            o.dest.add_overridden_profit(take)
            remaining_profit -= take

            o.value -= take
            if o.value < 0.01:
                self.profit_dest_overrides.pop(0)

        # Distribute profit to borrow events if any exist without the necessary
        # money to guarantee funding.
        borrow_event_tax_remaining = Decimal(float(remaining_profit) * 0.1)
        for borrow_event in reversed(self.borrow_events):
            if borrow_event.repay < borrow_event.funding:
                amount_to_repay = min(borrow_event.funding - borrow_event.repay, borrow_event_tax_remaining)
                remaining_profit -= amount_to_repay
                borrow_event.repay += amount_to_repay
                borrow_event_tax_remaining -= amount_to_repay
        remaining_profit += borrow_event_tax_remaining

        # Distribute remaining profit to borrow fund income stream if it is
        # below readiness threshold. And distribute a portion as tax if below
        # the tax threshold.
        if self.p.account.borrow_fund.is_in_danger(self.currency_kind):
            remaining_room = self.p.account.borrow_fund.get_income_ready_room(self.currency_kind)
            contribution = min(remaining_profit, remaining_room)
            remaining_profit -= contribution
            self.p.account.borrow_fund.add_income(contribution, self.currency_kind)
        if self.p.account.borrow_fund.is_taxed(self.currency_kind):
            contribution = Decimal(income_tax_rate * float(remaining_profit))
            remaining_profit -= contribution
            self.p.account.borrow_fund.add_income(contribution, self.currency_kind)

        # Distribute a portion to stages.
        for stage in self.stages:
            remaining_profit = stage.tax_profits(remaining_profit)

        self.p.add_profit(remaining_profit, currency=self.currency_kind)

        self.history.append(HistoryItem(datetime.now(), f"Sold {to_sell}", len(self)))

        return to_sell

    def buy_option(self, mode, date, strike_price, n_contracts, price=None,
            use_borrow_fund: bool = False) -> Option:
        ''' Buy a new option. '''
        self.fixup_price()

        if price is not None:
            price = Decimal(price)
        else:
            price = self.option_pricing.find(mode, date, strike_price, self.price)

        option = Option(self, mode, date, strike_price, n_contracts, price)
        self.p.account.currencies[self.currency_kind] -= n_contracts * 100 * price
        
        if use_borrow_fund:
            self.p.account.borrow_fund.add_income(-n_contracts * 100 * price, self.currency_kind)

        # Check if an identical option exists to combine with.
        identical_found = False
        for other_option in self.options:
            if other_option.is_identical_security(option):
                other_option.combine(option)
                option = other_option
                option.price = price
                identical_found = True
                break
        
        if not identical_found:
            self.options.append(option)

        return option

    def sell_option(self, o, n_contracts, price=None):
        ''' Sell n contracts. Any profit will be added to the borrow fund. '''
        self.fixup_price()
        if price is not None:
            o.price = Decimal(price)
        elif price is None and self.option_pricing is not None:
            o.price = self.option_pricing.find(o.mode, o.date, o.strike_price, self.price)

        sell_profit = o.sell(n_contracts, new_price=price)
        
        self.p.add_borrow_funding(sell_profit, currency=self.currency_kind)
        
        if o.n_contracts == 0:
            self.options.remove(o)

        self.p.account.currencies[self.currency_kind] += n_contracts * 100 * o.price
        return o
    
    def transform_option(self, o, n_contracts, price, old_option_price=None, mode=None, date=None,
            strike_price=None):
        ''' Transform n contracts into a new form. Any profit will be added to 
            the borrow fund. '''
        self.fixup_price()
        price = Decimal(price)
        
        if old_option_price is not None:
            o.price = Decimal(old_option_price)
        elif old_option_price is None and self.option_pricing is not None:
            o.price = self.option_pricing.find(o.mode, o.date, o.strike_price, self.price)

        if mode is None:
            mode = o.mode
        if date is None:
            date = o.date
        if strike_price is None:
            strike_price = o.strike_price

        new_option, sell_profit = o.transform(n_contracts, new_mode=mode, 
                new_date=date, new_strike=strike_price, new_price=price)
        if sell_profit > 0:
            self.p.add_borrow_funding(sell_profit, 
                    currency=self.currency_kind)
        elif sell_profit < 0:
            self.p.add_profit(sell_profit, currency=self.currency_kind)

        if o.n_contracts == 0:
            self.options.remove(o)

        # Check if an identical option exists to combine with.
        identical_found = False
        for other_option in self.options:
            if other_option.is_identical_security(new_option):
                other_option.combine(new_option)
                new_option = other_option
                new_option.price = price
                identical_found = True
                break
        
        if not identical_found:
            self.options.append(new_option)

        self.p.account.currencies[self.currency_kind] += n_contracts * 100 * o.price
        self.p.account.currencies[self.currency_kind] -= n_contracts * 100 * new_option.price
        return o, new_option

    def n_borrowed(self) -> int:
        ''' Get number of shares being borrowed. '''

        n_borrows = 0
        for borrow_event in self.borrow_events:
            n_borrows += borrow_event.n_shares
        return n_borrows

    def borrow(self, n, funding=None):
        ''' Borrow n shares at the current price. Physically selling them 
            while keeping them on as "virtual shares". 
            
            You can optionally specify funding which will be loaned from the
            borrow fund.    
        '''
        self.fixup_price()

        # Default to +20% rebuy threshold.
        if funding is None:
            funding = n * self.price * Decimal(0.2)

        self.p.account.borrow_fund.add_loan(funding, self.currency_kind)

        # Try to guarantee funding using the reserve.
        if funding > 0:
            available = currency_collection_get(self.p.account.borrow_fund.income, 
                    self.currency_kind)
            repay = min(available, funding)
            self.p.account.borrow_fund.add_income(-repay, self.currency_kind)
        else:
            repay = Decimal(0)

        now = datetime.now()
        tz = pytz.timezone('America/New_York')
        date = tz.localize(now).date()

        self.borrow_events.append(BorrowEvent(self.price, n, date, funding, repay))
        self.p.account.currencies[self.currency_kind] += self.price * n

    def unborrow(self, n=None):
        ''' Unborrow n shares at the current price. Physically re-buying them. '''
        self.fixup_price()

        borrow_events = deepcopy(self.borrow_events)
        n_remaining = n
        while 0 < len(borrow_events) and 0 < n_remaining:
            event = borrow_events[-1]

            old_n_shares = event.n_shares
            n_to_return = min(event.n_shares, n_remaining)
            n_remaining -= n_to_return
            event.n_shares -= n_to_return

            # Money loaned to this event was not actually taken out of the
            # reserve pool, it was just recorded as being loaned.
            loan_returned = Decimal(n_to_return / old_n_shares) * event.funding
            event.funding -= loan_returned
            self.p.account.borrow_fund.add_loan(-loan_returned, self.currency_kind)

            # Change reserve money based on the difference in borrow price and 
            # rebuy price. To be clear - this is the actual borrow price and 
            # not the rebuy threshold supported by borrow funding.
            rebuy_price_advantage = n_to_return * (event.price - self.price)
            
            # Money in the event's repayment will be added to the reserve
            # pool. We will use it in an attempt to offset the loss if
            # re-buying at a higher price than originally borrowed.
            if event.n_shares == 0:
                repayment_returned = event.repay
            elif rebuy_price_advantage >= 0:
                repayment_returned = 0
            else:
                repayment_returned = min(event.repay, -rebuy_price_advantage)
            event.repay -= repayment_returned
            self.p.account.borrow_fund.add_reserves(
                    rebuy_price_advantage + repayment_returned, 
                    self.currency_kind)

            if event.n_shares == 0:
                borrow_events.pop()

        if n_remaining > 0:
            raise Exception("Not enough borrowed shares to unborrow.")

        self.borrow_events = borrow_events
        self.p.account.currencies[self.currency_kind] -= self.price * n

    def unbind_all(self, exclude_horizon=True):
        ''' Unbind all shares. '''
        shares = self.shares[UNBOUND_SHARES] + self.shares[BOUND_SHARES]
        if not exclude_horizon:
            shares += self.shares[HORIZON_SHARES]

        self.shares[BOUND_SHARES] = Shares([])
        if not exclude_horizon:
            self.shares[HORIZON_SHARES] = Shares([])

        self.shares[UNBOUND_SHARES] = shares

    def unbound_to_horizon(self, n_shares):
        ''' Move the n most expensive unbound shares to horizon. '''

        top_n = self.shares[0].top(n_shares)
        self.shares[0] -= top_n
        self.shares[2] += top_n

    def horizon_to_unbound(self, n_shares):
        ''' Move the n least expensive horizon shares to unbound. '''

        bottom_n = self.shares[2].bottom(n_shares)
        self.shares[2] -= bottom_n
        self.shares[0] += bottom_n

    def move_top(self, n_shares, i0, i1):
        ''' Move the top n_shares from group i0 to i1'''

        top_n = self.shares[i0].top(n_shares)
        self.shares[i0] -= top_n
        self.shares[i1] += top_n
        
    def move_bottom(self, n_shares, i0, i1):
        ''' Move the bottom n_shares from group i0 to i1'''

        bottom_n = self.shares[i0].bottom(n_shares)
        self.shares[i0] -= bottom_n
        self.shares[i1] += bottom_n

    def get_highest_ready_price(self) -> Decimal:
        ''' Gets the highest supported price where on things like Ladders, any 
            rungs on the horizon will already be paid up to that point. '''
        
        # Of all stages that report ready prices, this is the minimum ready
        # price.
        min_stage_ready_price = Decimal(999999999)
        for stage in self.stages:
            min_stage_ready_price = min(min_stage_ready_price, 
                    stage.get_highest_ready_price())
        return min_stage_ready_price

    def reset_profit_levels(self):
        ''' Reset the profit levels of rung targets so that their start prices
            become min(current price, old start price). '''

        self.fixup_price()
        for stage in self.stages:
            stage.reset_profit_levels(self.price)

    def scale_profit_levels(self, scale: float):
        ''' Reset the profit levels of rung targets so that their start prices
            become min(current price, old start price). '''

        self.fixup_price()
        for stage in self.stages:
            stage.scale_profit_levels(scale, min_margin=MIN_SELL_GAIN)

    def enable_rungs(self):
        ''' Enable ladder rungs that were disabled. '''

        self.fixup_price()
        for stage in self.stages:
            stage.enable_rungs(self.price)

    def total_buy_cost(self):
        return self.shares.total_buy_cost()

    def get_money(self) -> Decimal:
        ''' Get amount of loose money. '''

        return self.p.account.currencies[self.currency_kind]

    def fixup_price(self):
        ''' Fixes up the price to be a proper Decimal. '''
        self.price = Decimal(penny_round(self.price))

    def apply_decay(self, n_days=None):
        ''' Apply stock price decay to account for leveraged ETF price decay
            over time relative to the underlying index.

            Return net cost of decay.
        '''
        
        if self.daily_decay_factor is None:
            return
        
        decay = lambda x, f, t: x * (1 - f) ** t
        decay_fn = lambda x: decay(x, self.daily_decay_factor, n_days)

        for stage in self.stages:
            stage.apply_decay_fn(decay_fn)

        decay_cost = Decimal(0)
        for (i, old_shares) in enumerate(self.shares):
            new_shares = Shares()
            for pair in old_shares.pairs:
                old_price = pair[0]
                n_shares = pair[1]
                new_price = penny_round(decay_fn(pair[0]))
                new_shares += [new_price, n_shares]
                decay_cost += (old_price - new_price) * n_shares

            self.shares[i] = new_shares
        
        borrow_decay = Decimal(0)
        for (i, e) in enumerate(self.borrow_events):
            old_price = e.price
            e.price = penny_round(decay_fn(e.price))
            borrow_decay += (old_price - e.price) * e.n_shares

        # Share price decay is considered negative (a loss/cost).
        # Borrow price decay encourages borrowing at a lower price than before
        # and so is considered positive (a gain).
        return decay_cost - borrow_decay

    def custom_target(self, sell_price, name,  profit, max_buy_price=None, 
            min_buy_price=None):
        ''' Create a custom target. 

            If max_buy_price or min_buy_price are None, they will be configured
                with reasonable defaults.  
        '''

        self.fixup_price()

        sell_price = Decimal(sell_price)
        profit = Decimal(profit)

        if max_buy_price is not None:
            max_buy_price = Decimal(max_buy_price)
        else:
            max_buy_price = Decimal(float(sell_price) / 1.01) 

        if min_buy_price is not None:
            min_buy_price = Decimal(max_buy_price)
        else:
            min_buy_price = self.price 

        # Find custom stage.
        custom_stage = None
        for stage in self.stages:
            if stage.get_stage_kind() == "custom":
                custom_stage = stage
                break

        if custom_stage is None:
            raise Exception("no custom stage!")
        
        custom_stage.new_target(sell_price, name, profit, max_buy_price, min_buy_price)

    def add_profit_dest_override(self, dest, value: Decimal):
        ''' Add an override destination where profits will go instead of the
            general profit account. '''
        
        # Combine any matching existing override.
        for o in self.profit_dest_overrides:
            if dest == o.dest:
                o.value += value
                return
        
        self.profit_dest_overrides.append(ProfitDestOverride(dest, value))

    def replace_from_dict(self, dict, context: SerializeContext):
        context.asset = self

        name = dict["name"]
        order = dict["order"]
        price = dict["price"]
        currency_kind = dict["currency"]
        shares = new_segregated_shares_from_dict(dict["shares"])
        surplus = dict["surplus"]
        base_change = Decimal(dict["baseChange"])

        self.name = name
        self.order = order
        self.price = Decimal(price)
        self.currency_kind = currency_kind
        self.shares = shares
        self.surplus = surplus
        self.options = [new_option_from_dict(d, context) for d in dict['options']]
        self.cached_targets = [new_target_from_dict(t, context) for t in dict["cachedTargets"]]
        self.stages = [new_stage_from_dict(s, context) for s in dict["stages"]]
        self.borrow_events = [new_borrow_event_from_dict(e) for e in dict["borrowEvents"]]
        self.history = [new_history_item_from_dict(d, context) for d in dict['history']]
        self.profit_dest_overrides = [new_profit_dest_override_from_dict(d, context) for d in dict['profitDestOverrides']]
        self.base_change = base_change

        self.daily_decay_factor = Decimal(dict["dailyDecayFactor"])

        self.margin_requirement = Decimal(dict["marginRequirement"])

        context.asset = None


def new_asset_from_dict(dict, portfolio, context: SerializeContext) -> Asset:
    ''' Creates a new asset from the given dictionary. '''

    asset = Asset(portfolio)
    asset.replace_from_dict(dict, context)
    return asset


def write_target_log(target, target_to_assignment) -> str:
    if isinstance(target, str):
        return "..."

    if target_to_assignment is not None:
        assignment = target_to_assignment.get(target, None)
    else:
        assignment = None
    if assignment is None:
        assignment_profit = 0
        assignment_shares = Shares()
    else:
        assignment_profit = assignment.profit
        assignment_shares = assignment.shares
    log = (f"${target.sell_price:.2f} ({target.name}) - Profit: " + 
            f"{assignment_profit:.2f}/{target.profit:.2f}; " +
            f"Max: {penny_round(target.max_buy_price):.2f}; " +
            f"Shares: {assignment_shares}")
    return log


if __name__ == '__main__':
    from pf import start
    p = start()
    a = p.assets[0]
    a.update()
    a.price = 71
    a.stages[0].targets[1].profit = 10
    print("------------")
    print("Update after new target set")
    a.update(True)
    print("Recommended sell remaining: ", a.recommended_sell)
    print(a)