class HarnessError(ValueError):
    def __init__(self, code, message, exit_code=2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def require(condition, message, code='INVALID_DATA', exit_code=2):
    if not condition:
        raise HarnessError(code, message, exit_code)
