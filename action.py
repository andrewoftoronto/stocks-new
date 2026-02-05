class Action:
    def __init__(self, name, pre_state=None, post_state=None):
        self.name = name
        self.pre_state = pre_state
        self.post_state = post_state

    def undo(self, pf):
        self.pf.load_from_dict(self.pre_state)

    def redo(self, pf):
        self.pf.load_from_dict(self.post_state)