from stage import StageBase
from custom import new_custom_from_dict
from ladder import new_ladder_from_dict
from option_stage import new_option_stage_from_dict
from serialize_context import SerializeContext


# Map of stage kinds to the function that creates them from json.
kind_to_load_fn = {}
kind_to_load_fn["custom"] = lambda d, c: new_custom_from_dict(d, c)
kind_to_load_fn["ladder"] = lambda d, c: new_ladder_from_dict(d, c)
kind_to_load_fn["option"] = lambda d, c: new_option_stage_from_dict(d, c)


def new_stage_from_dict(dict, context: SerializeContext) -> StageBase:
    stage_kind = dict["stage_kind"]
    return kind_to_load_fn[stage_kind](dict, context)