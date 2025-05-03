# Simulate update at given price and report the results without necessarily saving.

from decimal import Decimal
import argparse
from util import penny_round
from pf import start
p = start()

parser = argparse.ArgumentParser(description="Process price and allow_sells arguments.")
parser.add_argument("asset_index", type=int, help="The index of the asset")
parser.add_argument("price", type=float, help="The price as a float value")
parser.add_argument("allow_sells", type=lambda x: x.lower() == 't' or x.lower() == "true",
        help="Allow sells as a boolean (t/f)",  nargs="?", default=False)
parser.add_argument("-s", "--save", action="store_true", help="automatically save state after")

args = parser.parse_args()

a = p.assets[args.asset_index]
a.price = Decimal(args.price)
a.update(args.allow_sells)
a.summarize()

if args.save:
        print("Saving state...")
        p.save()