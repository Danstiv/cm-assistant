from functools import wraps
import sys

import pyrogram
from tgbot.states import state_storage

handlers = []


def get_handlers():
    return handlers


def clear_handlers():
    handlers.clear()


def make_handler_decorator(decorator_name):
    def handler_decorator(*handler_args, state=None, **handler_kwargs):
        def decorator(func):
            handler_name = func.__name__
            @wraps(func)
            async def wrapper(self, client, *args):
                nonlocal state
                if state is not None:
                    if isinstance(args[0], pyrogram.types.Message):
                        message = args[0]
                    elif isinstance(args[0], pyrogram.types.CallbackQuery):
                        message = args[0].message
                    else:
                        self.log.error(f'Обработчик {handler_name}. Возможность использования состояний не реализована для этого типа обработчиков.')
                        return
                    state_obj = await state[0].get_state(self, state[1], message.chat, message.from_user)
                    if not state_obj:
                        raise pyrogram.ContinuePropagation
                    state_storage.set(state_obj)
                try:
                    return await func(self, *args)
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
