class Portfolio:
    def __init__(self, account=None):
        self.account = account
        self.assets = []
        self.actions = []

    def push_action(self, name):
        self.actions.append(name)

    def record_action_post_state(self):
        #self.actions[-1].
        pass