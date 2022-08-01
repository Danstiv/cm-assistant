import contextvars


class EmptyContextVarException(Exception):
    pass
WRAPPABLE_MAGIC_METHODS = [
    '__pos__', '__neg__', '__abs__',
    '__invert__', '__round__', '__floor__',
    '__ceil__', '__trunc__', '__iadd__',
    '__isub__', '__imul__', '__ifloordiv__',
    '__idiv__', '__itruediv__', '__imod__',
    '__ipow__', '__ilshift__', '__irshift__',
    '__iand__', '__ior__', '__ixor__',
    '__int__', '__float__', '__complex__',
    '__oct__', '__hex__', '__index__',
    '__trunc__', '__str__', '__repr__',
    '__unicode__', '__format__', '__add__',
    '__sub__', '__mul__', '__floordiv__',
    '__truediv__', '__mod__', '__pow__',
    '__lt__', '__le__', '__eq__',
    '__ne__', '__ge__', '__getitem__',
    '__setitem__', '__delitem__', '__iter__',
    '__contains__', '__call__', '__enter__',
    '__exit__', '__bool__'
]


class ContextVarWrapperMetaClass(type):

    def __new__(cls, name, bases, dct):
        def make_method_proxy(name):
            def method_proxy(self, *args):
                return getattr(self.get_context_var_value(), name)(*args)
            return method_proxy
        for name in WRAPPABLE_MAGIC_METHODS:
            if name not in dct:
                dct[name] = make_method_proxy(name)
        return super().__new__(cls, name, bases, dct)


class ContextVarWrapper(metaclass=ContextVarWrapperMetaClass):
    def __init__(self, context_var_name):
        self.__dict__['context_var'] = contextvars.ContextVar(context_var_name)

    def set_context_var_value(self, *args, **kwargs):
        self.context_var.set(*args, **kwargs)

    def get_context_var_value(self, *args, **kwargs):
        try:
            return self.context_var.get(*args, **kwargs)
        except LookupError:
            raise EmptyContextVarException(f'Context var "{self.context_var.name}" is empty')

    @property
    def is_set(self):
        try:
            self.get_context_var_value()
            return True
        except EmptyContextVarException:
            return False

    def __getattr__(self, name):
        return getattr(self.get_context_var_value(), name)

    def __setattr__(self, name, value):
        return setattr(self.get_context_var_value(), name, value)
