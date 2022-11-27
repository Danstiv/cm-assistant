import contextvars

_EMPTY_PLACEHOLDER = type('EmptyPlaceholder', (), {})()

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


class ContextVarWrapperException(Exception):
    pass


class EmptyContextVarException(ContextVarWrapperException):
    pass


class AccessToContextVarValueRestrictedError(ContextVarWrapperException):
    pass


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
        self.set_context_var_value(_EMPTY_PLACEHOLDER)

    def set_context_var_value(self, value):
        if hasattr(value, 'access_to_context_var_value_restricted'):
            del value.access_to_context_var_value_restricted
        self.context_var.set(value)

    def get_context_var_value(self, ignore_restrictions=False):
        try:
            value = self.context_var.get()
            if value is _EMPTY_PLACEHOLDER:
                raise LookupError
            if not ignore_restrictions and getattr(value, 'access_to_context_var_value_restricted', False):
                raise AccessToContextVarValueRestrictedError(f'Access to the value of the context var "{self.context_var.name}" is restricted')
            return value
        except LookupError:
            raise EmptyContextVarException(f'Context var "{self.context_var.name}" is empty')

    def reset_context_var(self):
        self.context_var.set(_EMPTY_PLACEHOLDER)

    @property
    def is_set(self):
        try:
            self.get_context_var_value()
            return True
        except AccessToContextVarValueRestrictedError:
            return True
        except EmptyContextVarException:
            return False

    def restrict_access_to_context_var_value(self):
        try:
            value = self.get_context_var_value()
        except AccessToContextVarValueRestrictedError:
            raise AccessToContextVarValueRestrictedError(f'Access to the value of the context var "{self.context_var.name}" is already restricted')
        try:
            value.access_to_context_var_value_restricted = True
        except AttributeError:
            raise ContextVarWrapperException('This value cannot be restricted')

    def __getattr__(self, name):
        return getattr(self.get_context_var_value(), name)

    def __setattr__(self, name, value):
        return setattr(self.get_context_var_value(), name, value)
