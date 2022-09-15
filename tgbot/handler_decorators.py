import copy
import inspect
import re
import sys

import pyrogram

handlers = []
SNAKE_TO_CAMEL_CASE_REGEX = re.compile(r'^.|_.')

def get_handlers():
    return copy.deepcopy(handlers)


def clear_handlers():
    handlers.clear()


def make_handler_decorator(handler):
    def handler_decorator(*handler_args, **handler_kwargs):
        def decorator(func):
            if not inspect.iscoroutinefunction(func):
                raise ValueError(f'{func.__name__} handler is not a coroutine')
            handler_info = {
                'handler': handler,
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
    handler_name = SNAKE_TO_CAMEL_CASE_REGEX.sub(lambda m: m[0][-1].upper(), attr[3:]) + 'Handler'
    handler = getattr(pyrogram.handlers, handler_name)
    setattr(module, attr, make_handler_decorator(handler))
del module
