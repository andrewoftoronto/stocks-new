import json
from decimal import Decimal


def load(file_name, noexcept=False):
    try:
        f = open(file_name, "r")
        data = f.read()
        f.close()
        return json.loads(data)
    except Exception as e:
        if noexcept:
            print("Failed to load:", file_name, "due to", e)
            return None
        else:
            raise e
    

def save(file_name, data):
    dump = json.dumps(data, default=lambda x: float(x) if isinstance(x, Decimal) else x)
    f = open(file_name, "w")
    f.write(dump)
    f.close()