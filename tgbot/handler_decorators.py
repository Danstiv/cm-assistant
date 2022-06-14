from functools import wraps
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
            handler_name = func.__name__
            @wraps(func)
            async def wrapper(self, client, *args, **kwargs):
                try:
                    return await func(self, *args, **kwargs)
                except (pyrogram.ContinuePropagation, pyrogram.StopPropagation):
                    raise
                except Exception:
                    self.log.exception(f'В обработчике {handler_name} произошло необработанное исключение:')
            handler_info = {
                'decorator_name': decorator_name,
                'handler_args': handler_args,
                'handler_kwargs': handler_kwargs,
                'handler_name': handler_name,
            }
            handlers.append(handler_info)
            return wrapper
        return decorator
    return handler_decorator

module = sys.modules[__name__]
for attr in dir(pyrogram.Client):
    if not attr.startswith('on_'):
        continue
    setattr(module, attr, make_handler_decorator(attr))
del module
