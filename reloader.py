import asyncio
from importlib import reload
import sys

import cm_assistant
import tgbot


async def reload_bot(controller=None):
    modules = []
    for module in list(sys.modules.values()):
        if hasattr(module, '__package__') and module.__package__.startswith('tgbot'):
            modules.append(module)
    [reload(module) for _ in range(2) for module in modules]
    reload(cm_assistant)
    if controller:
        controller.stop()
        while controller.app.is_initialized:
            await asyncio.sleep(0.01)
        controller.log.handlers = []
    controller = cm_assistant.Controller()
    asyncio.create_task(controller.start())
    return controller
