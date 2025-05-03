from datetime import datetime
from serialize_context import SerializeContext


class HistoryItem:
    ''' Describes an action in the history of an asset. '''

    def __init__(self, time: datetime, description: str, physical_shares: int):
        self.time = time
        self.description = description
        self.physical_shares = physical_shares

    def to_dict(self, context: SerializeContext):
        return {
            "time": str(self.time),
            "description": self.description,
            "physicalShares": self.physical_shares
        }

    def __repr__(self) -> str:
        return f"{self.time}: {self.description} ({self.physical_shares} shares after)"

def new_history_item_from_dict(dict, context: SerializeContext) -> HistoryItem:
    return HistoryItem(dict['time'], dict['description'], dict['physicalShares'])