''' Reduce targets to save on costs. '''

from decimal import Decimal
import argparse
from util import penny_round
from pf import start
from find_borrows import find_borrows
p = start()


parser = argparse.ArgumentParser(description="")
parser.add_argument("asset_index", type=int, help="The index of the asset")
parser.add_argument("change", type=float, help="Change in base profit level")
parser.add_argument("-s", "--save", action="store_true", help="automatically save state after")

args = parser.parse_args()

base_d_profit = Decimal(args.change)
base_sell_times = Decimal(1.015)

a = p.assets[args.asset_index]
a.base_change += base_d_profit 
for rung in a.stages[1].rung_defs:
    d_profit = base_d_profit * rung.sell_times / base_sell_times
    rung.profit += d_profit
    rung.min_profit += d_profit

print("Base change:", a.base_change)

if args.save:
        print("Saving state...")
        p.save()

find_borrows(p, a)
