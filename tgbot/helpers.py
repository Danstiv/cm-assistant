class EmptyContextVarException(Exception):
    pass


class ContextVarWrapper:
    def __init__(self, var):
        self.__dict__['var'] = var

    def get(self, *args, **kwargs):
        try:
            return self.var.get(*args, **kwargs)
        except LookupError:
            raise EmptyContextVarException(f'Context var {self.var.name} is empty')

    def __getattr__(self, name):
        return getattr(self.get(), name)

    def __setattr__(self, name, value):
        return setattr(self.get(), name, value)
