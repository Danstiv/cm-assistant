import datetime

from tgbot.enums import PaginatorMode
from tgbot.gui import BaseTab
from tgbot.gui.buttons import SimpleButton
from tgbot.gui.tabs import Tab

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


class PaginatedTabMixin(Tab):
    mode = PaginatorMode.STANDARD
    add_page_info_into_text = True

    async def build(self, *args, page_number=1, **kwargs):
        await super().build(*args, **kwargs)
        await self.update(page_number)

    async def set_page(self, page):
        raise NotImplementedError

    async def set_next_page(self):
        raise NotImplementedError

    async def set_previous_page(self):
        raise NotImplementedError

    async def update(self, page_number):
        self.keyboard.clear()
        use_page_numbers = self.mode != PaginatorMode.NO_PAGES
        if use_page_numbers:
            info = await self.set_page(page_number)
        else:
            info = await (self.set_previous_page if page_number == -1 else self.set_next_page)()
        total_pages = info.pop('total_pages', None)
        is_first_page = info.pop('is_first_page', False)
        is_last_page = info.pop('is_last_page', False)
        if use_page_numbers and self.add_page_info_into_text:
            line = f'Страница {page_number}'
            if total_pages is not None:
                line += f' / {total_pages}'
            line += '.'
            self.text.append_to_body('\n\n' + line)
        # if use_page_numbers is False - simple scrolling without page numbers
        if use_page_numbers:
            is_first_page = page_number == 1
            # if total_pages is None - infinite scrolling
            if total_pages is not None:  # Regular paginated set of fixed size
                is_last_page = page_number == total_pages
        first_buttons_row = []
        last_buttons_row = []
        if not use_page_numbers:
            if not is_first_page:
                first_buttons_row.append(SimpleButton(
                    '<',
                    name='page_button',
                    callback=self.on_previous_page,
                ))
            if not is_last_page:
                first_buttons_row.append(SimpleButton(
                    '>',
                    name='page_button',
                    callback=self.on_next_page,
                ))
        else:
            if not is_last_page:
                first_buttons_row.append(SimpleButton(
                    str(page_number + 1),
                    name='page_button',
                    callback=self.on_page,
                    arg=page_number + 1
                ))
                if total_pages is not None:
                    for p in range(page_number + 2, page_number + min(4, total_pages - page_number)):
                        first_buttons_row.append(SimpleButton(
                            str(p),
                            name='page_button',
                            callback=self.on_page,
                            arg=p
                        ))
                    if page_number + 1 < total_pages:
                        first_buttons_row.append(SimpleButton(
                            str(total_pages),
                            name='page_button',
                            callback=self.on_page,
                            arg=total_pages
                        ))
            if not is_first_page:
                last_buttons_row.append(SimpleButton(
                    str(page_number - 1),
                    name='page_button',
                    callback=self.on_page,
                    arg=page_number - 1
                ))
                for p in list(range(max(2, page_number - 3), page_number - 1)):
                    last_buttons_row.insert(-1, SimpleButton(
                        str(p),
                        name='page_button',
                        callback=self.on_page,
                        arg=p
                    ))
                if page_number > 2:
                    last_buttons_row.insert(0, SimpleButton(
                        '1',
                        name='page_button',
                        callback=self.on_page,
                        arg=1
                    ))
        self.keyboard.add_row(*first_buttons_row)
        self.keyboard.add_row(*last_buttons_row)

    async def on_page(self, arg):
        await self.update(int(arg))

    async def on_next_page(self, arg):
        await self.update(1)

    async def on_previous_page(self, arg):
        await self.update(-1)
