import asyncio
import time


class Limiter:
    def __init__(self, controller, amount, period, static=True, name=None):
        self.controller = controller
        self.amount = amount
        self.period = period
        self.static = static
        self.name = name
        self.events = [0]*self.amount
        self.full_name = 'лимитер' if not self.name else 'лимитер '+self.name
        self.controller.log.debug(f'Создан {self.full_name} ({self.amount} событий за {self.period} секунд)')

    async def __call__(self):
        delay = max(self.period-(time.time()-self.events[0]), 0)
        self.controller.log.debug(f'{self.full_name}: задержка {round(delay, 3)}')
        self.events.append(time.time()+delay)
        del self.events[0]
        if delay > 0:
            await asyncio.sleep(delay)

    @property
    def is_old(self):
        return not self.static and time.time() - self.events[-1] >= self.period
