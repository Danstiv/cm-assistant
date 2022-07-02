import binascii
import datetime
import uuid

import pyrogram
from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, String, select
from sqlalchemy.orm import declarative_mixin

from tgbot.constants import DEFAULT_USER_ID
from tgbot.handler_decorators import on_callback_query
from tgbot.helpers import ContextVarWrapper


current_callback_query = ContextVarWrapper('current_callback_query')

CRC32_BUTTON_CLASSES_MAP = {}
CRC32_KEYBOARD_CLASSES_MAP = {}

def store_class_crc32(class_, map):
    crc32 = binascii.crc32(class_.__name__.encode())
    crc32 = crc32.to_bytes(4, 'little')
    if crc32 in map:
        if map[crc32].__name__ == class_.__name__:
            raise ValueError(f'Class {class_.__name__} already registered')
        raise ValueError(f'CRC32 for classes {map[crc32].__name__} and {class_.__name__} matched!')
    class_.crc32 = crc32
    map[crc32] = class_

def button_decorator(button_class):
    store_class_crc32(button_class, CRC32_BUTTON_CLASSES_MAP)
    return button_class

def keyboard_decorator(keyboard_class):
    store_class_crc32(keyboard_class, CRC32_KEYBOARD_CLASSES_MAP)
    return keyboard_class


@declarative_mixin
class BaseButtonMixin:
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, default=DEFAULT_USER_ID)
    button_id = Column(Integer, nullable=False)
    creation_date = Column(DateTime, nullable=False)
    callback_data = Column(LargeBinary(24), unique=True, nullable=False)
    answer = Column(Boolean, default=True)


class ButtonMixin(BaseButtonMixin):
    callback_name = Column(String)


class BaseKeyboard:

    @classmethod
    async def create_keyboard(cls, controller, keyboard, callback=None):
        inline_keyboard = []
        db_buttons = []
        dt = datetime.datetime.now()
        button_id = 0
        for keyboard_row in keyboard:
            inline_keyboard_row = []
            for keyboard_button in keyboard_row:
                if 'inline_kwargs' in keyboard_button:
                    inline_keyboard_row.append(pyrogram.types.InlineKeyboardButton(keyboard_button['name'], **keyboard_button['inline_kwargs']))
                    continue
                if 'table' in keyboard_button:
                    row = keyboard_button['table'](**keyboard_button.get('kwargs', {}))
                elif 'row' in keyboard_button:
                    row = keyboard_button['row']
                else:
                    raise ValueError('Neither table nor row specified')
                row.creation_date = dt
                row.button_id = button_id
                button_id += 1
                row.callback_data = row.crc32 + cls.crc32 + uuid.uuid4().bytes
                callback = keyboard_button.get('callback', None) or callback
                if callback:
                    row.callback_name = callback.__name__
                db_buttons.append(row)
                inline_keyboard_row.append(pyrogram.types.InlineKeyboardButton(keyboard_button['name'], callback_data=row.callback_data))
            inline_keyboard.append(inline_keyboard_row)
        async with controller.db.begin() as db:
            db.add_all(db_buttons)
        controller.temp = db_buttons
        return pyrogram.types.InlineKeyboardMarkup(inline_keyboard)


@keyboard_decorator
class SimpleKeyboard(BaseKeyboard):

    @classmethod
    async def handle_button_activation(cls, controller, callback_query, keyboard, row_index, column_index):
        button = keyboard[row_index][column_index]
        await getattr(controller, button.callback_name)(button)


class KeyboardHandler:

    @on_callback_query()
    async def handle_callback_query(self, callback_query):
        try:
            callback_data = callback_query.data
            if len(callback_data) != 24:
                raise ValueError
            table = CRC32_BUTTON_CLASSES_MAP.get(callback_data[:4])
            keyboard_class = CRC32_KEYBOARD_CLASSES_MAP.get(callback_data[4:8])
            if not table or not keyboard_class:
                raise ValueError
            result_keyboard = []
            db_buttons = []
            tables_data_map = {}
            row_index = None
            column_index = None
            buttons_with_callback_data = 0
            for current_row_index, row in enumerate(callback_query.message.reply_markup.inline_keyboard):
                result_row = []
                for current_column_index, button in enumerate(row):
                    if button.callback_data is None:
                        result_row.append(None)
                        continue
                    buttons_with_callback_data += 1
                    result_row.append(42)
                    table = CRC32_BUTTON_CLASSES_MAP[button.callback_data[:4]]
                    if table not in tables_data_map:
                        tables_data_map[table] = []
                    tables_data_map[table].append(button.callback_data)
                    if row_index is not None or button.callback_data != callback_query.data:
                        continue
                    row_index = current_row_index
                    column_index = current_column_index
                result_keyboard.append(result_row)
            if row_index is None:
                raise ValueError
            async with self.db.begin() as db:
                for table, buttons_data in tables_data_map.items():
                    stmt = select(table).where(
                        table.callback_data.in_(buttons_data)
                    )
                    db_buttons.extend(list((await db.execute(stmt)).scalars()))
            if len(db_buttons) != buttons_with_callback_data:
                raise ValueError
            db_buttons.sort(key=lambda b: b.button_id)
            for current_row_index, row in enumerate(result_keyboard):
                for current_column_index, placeholder in enumerate(row):
                    if placeholder == 42:
                        result_keyboard[current_row_index][current_column_index] = db_buttons.pop(0)
        except ValueError:
            await callback_query.answer('Извините, эта клавиатура устарела и больше не обслуживается. Пожалуйста, попробуйте воспользоваться клавиатурой из более позднего сообщения.', show_alert=True)
            return
        activated_button = result_keyboard[column_index][row_index]
        if activated_button.user_id != DEFAULT_USER_ID and callback_query.from_user.id != activated_button.user_id:
            await callback_query.answer('Извините, вы не можете активировать эту кнопку.', show_alert=True)
        if activated_button.answer:
            await callback_query.answer()
        else:
            current_callback_query.set_context_var(callback_query)
        await keyboard_class.handle_button_activation(self, callback_query, result_keyboard, row_index, column_index)
