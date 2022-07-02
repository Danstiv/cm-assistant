import contextvars


class EmptyContextVarException(Exception):
    pass


class ContextVarWrapper:
    def __init__(self, context_var_name):
        self.__dict__['context_var'] = contextvars.ContextVar(context_var_name)

    def set_context_var_value(self, *args, **kwargs):
        self.context_var.set(*args, **kwargs)

    def get_context_var_value(self, *args, **kwargs):
        try:
            return self.context_var.get(*args, **kwargs)
        except LookupError:
            raise EmptyContextVarException(f'Context var {self.context_var.name} is empty')

    def __getattr__(self, name):
        return getattr(self.get_context_var_value(), name)

    def __setattr__(self, name, value):
        return setattr(self.get_context_var_value(), name, value)
