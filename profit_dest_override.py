from serialize_context import SerializeContext
from decimal import Decimal


class ProfitDestOverride:
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value

    def to_dict(self, ctx: SerializeContext):
        return {
            "destID": self.dest.get_serialize_id(ctx),
            "value": self.value
        }

def new_profit_dest_override_from_dict(d, ctx: SerializeContext):
    dest = ctx.id_to_value[d["destID"]]
    value = Decimal(d["value"])
    return ProfitDestOverride(dest, value)