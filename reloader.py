import asyncio
from importlib import reload
import sys

import cm_assistant
import tgbot


def reload_bot(controller):
    modules = []
    for module in sys.modules.values():
        if hasattr(module, '__file__') and isinstance(module.__file__, str) and '\\tgbot\\' in module.__file__:
            modules.append(module)
    [reload(module) for _ in range(2) for module in modules]
    reload(cm_assistant)
    if controller:
        controller.stop()
        controller.log.handlers = []
    controller = cm_assistant.Controller()
    asyncio.create_task(controller.start())
    return controller
