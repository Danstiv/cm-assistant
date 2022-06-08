import time
import uuid

import pyrogram
from sqlalchemy import select
from .db.tables import Button
from .handler_decorators import on_callback_query


class KeyboardHandler:

    async def create_keyboard(self, keyboard_data, default_callback=None):
        if default_callback is not None:
            default_callback = default_callback.__name__ if callable(default_callback) else default_callback
        keyboard = []
        db_buttons = []
        for row_data in keyboard_data:
            row = []
            for button_data in row_data:
                if isinstance(button_data, str):
                    button_name = button_data
                else:
                    button_name = button_data[0]
                    if len(button_data) == 1:
                        if not default_callback:
                            raise ValueError('No callback for button. Pass default_callback or set it explicitly for each button')
                        callback_name = default_callback
                    else:
                        callback_name = button_data[1].__name__ if callable(button_data[1]) else button_data[1]
                callback_data = str(uuid.uuid4())
                db_button = Button(creation_date=int(time.time()), callback_data=callback_data, callback_name=callback_name)
                db_buttons.append(db_button)
                button = pyrogram.types.InlineKeyboardButton(text=button_name, callback_data=callback_data)
                row.append(button)
            keyboard.append(row)
        self.db.add_all(db_buttons)
        await self.db.commit()
        return pyrogram.types.InlineKeyboardMarkup(keyboard)

    @on_callback_query()
    async def handle_callback_query(self, callback_query):
        callback_data = str(callback_query.data)
        stmt = select(Button).where(
            Button.callback_data == callback_data
        )
        db_button = (await self.db.execute(stmt)).scalar()
        if not db_button:
            await callback_query.answer('Извините, эта клавиатура устарела и больше не обслуживается. Пожалуйста, попробуйте воспользоваться клавиатурой из более позднего сообщения.', show_alert=True)
            return
        await callback_query.answer()
        await getattr(self, db_button.callback_name)(callback_query, db_button)

    async def test_buttons(self, *args):
        await self.send_message('Working!')
