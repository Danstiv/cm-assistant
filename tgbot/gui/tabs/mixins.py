import datetime

from tgbot.gui import BaseTab
from tgbot.gui.buttons import SimpleButton

YEAR = datetime.timedelta(days=365)
MONTH = datetime.timedelta(days=30)
DAY = datetime.timedelta(days=1)
HOUR = datetime.timedelta(hours=1)
MINUTE = datetime.timedelta(minutes=1)
SECOND = datetime.timedelta(seconds=1)


class DateTimeSelectionTabMixin(BaseTab):

    async def build(self, *args, **kwargs):
        await super().build(*args, **kwargs)
        await self.set_date_buttons()

    async def get_text_data(self):
        return {
            'date_time': await self.get_date_time(),
        }

    async def set_date_buttons(self, arg=None):
        await self.keyboard.remove_buttons_by_name('date_time_button')
        self.keyboard.buttons = [
            [
                SimpleButton('-г', arg=-1, callback=self.on_year_btn, name='date_time_button'),
                SimpleButton('+г', arg=1, callback=self.on_year_btn, name='date_time_button'),
            ], [
                SimpleButton('-м', arg=-1, callback=self.on_month_btn, name='date_time_button'),
                SimpleButton('+м', arg=1, callback=self.on_month_btn, name='date_time_button'),
            ], [
                SimpleButton('-д', arg=-1, callback=self.on_day_btn, name='date_time_button'),
                SimpleButton('+д', arg=1, callback=self.on_day_btn, name='date_time_button'),
            ],
            [SimpleButton('Выбрать время', callback=self.set_time_buttons, name='date_time_button')],
            *self.keyboard.buttons,
        ]

    async def on_year_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + YEAR * int(arg))

    async def on_month_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + MONTH * int(arg))

    async def on_day_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + DAY * int(arg))

    async def set_time_buttons(self, arg=None):
        await self.keyboard.remove_buttons_by_name('date_time_button')
        self.keyboard.buttons = [
            [
                SimpleButton('-ч', arg=-1, callback=self.on_hour_btn, name='date_time_button'),
                SimpleButton('+ч', arg=1, callback=self.on_hour_btn, name='date_time_button'),
            ], [
                SimpleButton('-м', arg=-1, callback=self.on_minute_btn, name='date_time_button'),
                SimpleButton('+м', arg=1, callback=self.on_minute_btn, name='date_time_button'),
            ], [
                SimpleButton('-с', arg=-1, callback=self.on_second_btn, name='date_time_button'),
                SimpleButton('+с', arg=1, callback=self.on_second_btn, name='date_time_button'),
            ],
            [SimpleButton('Выбрать дату', callback=self.set_date_buttons, name='date_time_button')],
            *self.keyboard.buttons,
        ]

    async def on_hour_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + HOUR * int(arg))

    async def on_minute_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + MINUTE * int(arg))

    async def on_second_btn(self, arg):
        await self.set_date_time(await self.get_date_time() + SECOND * int(arg))
