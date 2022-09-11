import inspect
import sys

import pyrogram

handlers = []


def get_handlers():
    return handlers


def clear_handlers():
    handlers.clear()


def make_handler_decorator(decorator_name):
    def handler_decorator(*handler_args, **handler_kwargs):
        def decorator(func):
            if not inspect.iscoroutinefunction(func):
                raise ValueError(f'{func.__name__} handler is not a coroutine')
            handler_info = {
                'decorator_name': decorator_name,
                'handler_args': handler_args,
                'handler_kwargs': handler_kwargs,
                'handler_name': func.__name__,
            }
            handlers.append(handler_info)
            return func
        return decorator
    return handler_decorator

module = sys.modules[__name__]
for attr in dir(pyrogram.Client):
    if not attr.startswith('on_'):
        continue
    setattr(module, attr, make_handler_decorator(attr))
del module
