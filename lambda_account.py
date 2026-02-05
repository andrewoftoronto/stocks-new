class LambdaAccount:
    ''' Account/line item whose value is calculated using a lambda. '''

    def __init__(self, fn):
        self.fn = fn

    def total(self):
        return self.fn()