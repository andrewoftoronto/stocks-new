from typing import List, Dict
from decimal import Decimal
from math import ceil
from target import Target
from shares import Shares, pair_n_needed_for_profit
from assignment import Assignment
from search_helper import binary_search, exponential_binary_search


class DistributionReport:
    ''' Report on distributing shares to targets. '''

    def __init__(self, target_to_assignment: Dict[Target, Assignment], 
            unbound_shares: Shares, all_satisfied: bool, 
            buyables_satisfied: bool, buys_needed: int=None):
        self.target_to_assignment = target_to_assignment
        self.unbound_shares = unbound_shares

        # Wether all targets are satisfied.
        self.all_satisfied = all_satisfied

        # Whether all targets that can be satisfied by buying at the current
        # price have been satisfied. Even when this is true, there may be 
        # targets where the max-buy is lower than current price that are
        # unsatisfied.
        self.buyables_satisfied = buyables_satisfied

        # Might not be set if the distribution function did not compute it.
        self.buys_needed = buys_needed


def distribute(shares: Shares, targets: List[Target], current_price: Decimal,
        min_margin: float) -> DistributionReport:
    ''' Distribute the given shares to the given targets, returning a set of
        share->target assignments and a set of unbound shares.
         
        This algorithm considers min-buy-price, with targets passing over 
        lower priced shares in favour of higher priced ones when it would make
        sense.
    '''

    first_report = distribute_pass(shares, targets, current_price, min_margin)
    if not first_report.buyables_satisfied:

        # We need to buy more shares.
        def callback(n_try_buy):
            try_shares = shares + [current_price, n_try_buy]
            report = distribute_pass(try_shares, targets, current_price, 
                min_margin)
            return not report.buyables_satisfied
        
        # We have to add 1 because the n we're looking for is the first time
        # that the function returns false.
        n_to_buy = exponential_binary_search(callback, 0, 32) + 1
        first_report.buys_needed = n_to_buy
        return first_report
    
    elif first_report.all_satisfied and len(first_report.unbound_shares) > 0:
        
        # We probably have extra shares.

        # See how many shares we can sell.
        def callback(n_try_sell):
            try_shares = shares - shares.bottom(n_try_sell)
            report = distribute_pass(try_shares, targets, current_price, 
                min_margin)
            return report.all_satisfied
        n_sell = binary_search(callback, 0, len(shares))

        if n_sell == 0:
            return first_report
        else:
            held_out_shares = shares.bottom(n_sell)
            retained_shares = shares - held_out_shares
            report = distribute_pass(retained_shares, targets, current_price, 
                    min_margin)
            report.unbound_shares += held_out_shares
            return report
    else:
        return first_report


def distribute_pass(shares: Shares, targets: List[Target], current_price: Decimal,
        min_margin: float) -> DistributionReport:
    ''' A single pass of the distribute algorithm. Attempts to assign the given
        shares to all targets, starting from the bottom-most target and the 
        cheapest shares. '''

    targets = sorted(targets, key=lambda t: (t.max_buy_price, t.sell_price))
    target_to_assignment = {}

    remaining_shares = shares.clone()
    all_satisfied = True
    buyables_satisfied = True
    for target in targets:

        assignment = Assignment(target, Shares(), 0)
        target_to_assignment[target] = assignment
        while 0 < len(remaining_shares):

            if target.profit <= assignment.profit:
                break

            pair = remaining_shares.pairs[0]
            if target.max_buy_price < pair[0]:

                # This pair is ineligible to satisfy this target and so would any
                # more expensive shares.
                break

            # If this is below min_buy_price, check for alternatives.
            if pair[0] < target.min_buy_price:

                # We will choose the highest scoring alternative. The loop
                # will consider the original pair as well.
                chosen_pair = None
                best_score = None
                for alternative_pair in remaining_shares.pairs:
                    if target.max_buy_price < alternative_pair[0]:
                        break

                    is_above = target.min_buy_price <= alternative_pair[0]
                    score = (target.sell_price - max(alternative_pair[0], target.min_buy_price))
                    if not is_above:
                        score -= target.min_buy_price - alternative_pair[0]

                    if best_score is None or best_score < score:
                        chosen_pair = alternative_pair
                        best_score = score

                    if is_above:
                        break

            else:
                chosen_pair = pair

            profit_needed = target.profit - assignment.profit
            n_shares, profit = pair_n_needed_for_profit(chosen_pair, profit_needed,
                    target.sell_price, target.min_buy_price, min_margin)
            if 0 < n_shares:
                taken_shares = [chosen_pair[0], n_shares]
                remaining_shares -= taken_shares
                assignment.profit += profit
                assignment.shares += taken_shares
            elif n_shares == 0:
                print("Error diagnostics:")
                print("  Chosen Pair:", chosen_pair)
                raise Exception("Somehow n_shares = 0")

        if assignment.profit < target.profit:

            # buyables_satisfied is only set to false if it is possible to buy 
            # more shares to satisfy the target.
            could_buy_to_satisfy = current_price <= target.max_buy_price
            all_satisfied = False
            buyables_satisfied = buyables_satisfied and (not could_buy_to_satisfy)

    return DistributionReport(target_to_assignment, remaining_shares, 
            all_satisfied, buyables_satisfied)
            

if __name__ == '__main__':
    
    def test_report(report):

        kv = report.target_to_assignment.items()
        kv = sorted(kv, key=lambda x: x[0].sell_price, reverse=True)
        for (k, v) in kv:
            print(f"  {k.name} ${k.sell_price} ({v.profit}/{k.profit}): {v.shares}")
        print("  Unbound: ", report.unbound_shares)
        print("  Buys needed:", report.buys_needed)

    def test_1():
        print("Test 1:")

        # This test scenario would likely trip up the old algorithm. We consider
        # the idea that t3 was just introduced, while t2 and t1 already existed.
        shares = Shares([[0.05, 5], [0.1, 2], [40, 5]])
        t1 = Target("t1", 35, 50, 50.0, 0)
        t3 = Target("t3", 35, 48, 47.0, 40)
        t2 = Target("t2", 35, 45, 44.0, 0)
        targets = [t1, t3, t2]
        report = distribute(shares, targets, 40, 1.01)
        test_report(report)

        print("  After selling as the report said:")
        shares -= report.unbound_shares
        report = distribute(shares, targets, 40, 1.01)
        test_report(report)

    def test_2():
        print("Test 2:")

        # See what happens when we need to buy shares.
        shares = Shares([[0.1, 2]])
        t1 = Target("t1", 35, 50, 50.0, 0)
        t3 = Target("t3", 35, 48, 47.0, 40)
        t2 = Target("t2", 35, 45, 44.0, 0)
        targets = [t1, t3, t2]
        report = distribute(shares, targets, 40, 1.01)
        test_report(report)

        print("  After buying as the report said:")
        shares += [[40, report.buys_needed]]
        report = distribute(shares, targets, 40, 1.01)
        test_report(report)

    test_1()
    test_2()
            
    
