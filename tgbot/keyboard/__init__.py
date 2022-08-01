import binascii
import datetime
import uuid

import pyrogram
from sqlalchemy import select

from tgbot.constants import DEFAULT_USER_ID
from tgbot.db import db, tables
from tgbot.handler_decorators import on_callback_query
from tgbot.helpers import ContextVarWrapper
from tgbot.helpers.sqlalchemy_row_wrapper import SQLAlchemyRowWrapper



current_callback_query = ContextVarWrapper('current_callback_query')

CRC32_BUTTON_CLASSES_MAP = {}

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


class BaseButton(SQLAlchemyRowWrapper):

    def __init__(self, controller, row=None, **kwargs):
        self.controller = controller
        self.row = row if row else self.table(**kwargs)

    async def handle_button_activation(self, controller, keyboard, row_index, column_index):
        raise NotImplementedError

    def get_inline_button_name(self, clean_name):
        return clean_name


class Button(BaseButton):

    async def handle_button_activation(self, keyboard, row_index, column_index):
        button = keyboard[row_index][column_index]
        await getattr(self.controller, button.callback_name)(keyboard, button, row_index, column_index)


@button_decorator
class SimpleButton(Button):
    table = tables.SimpleButton


class CheckBoxButton(BaseButton):

    async def handle_button_activation(self, keyboard, row_index, column_index):
        button = keyboard[row_index][column_index]
        inline_button = current_callback_query.message.reply_markup.inline_keyboard[row_index][column_index]
        if button.is_checked:
            inline_button.text = button.unchecked_prefix + inline_button.text[len(button.checked_prefix):]
        else:
            inline_button.text = button.checked_prefix + inline_button.text[len(button.unchecked_prefix):]
        button.is_checked = not button.is_checked
        await button.save()
        await current_callback_query.message.edit_reply_markup(current_callback_query.message.reply_markup)

    def get_inline_button_name(self, clean_name):
        temp = self.__table__.c
        prefix = temp['checked_prefix'].default.arg if self.is_checked else temp['unchecked_prefix'].default.arg
        return prefix + clean_name


@button_decorator     
class SimpleCheckBoxButton(CheckBoxButton):
    table = tables.SimpleCheckBoxButton


async def create_keyboard(controller, keyboard):
    inline_keyboard = []
    db_buttons = []
    dt = datetime.datetime.now()
    for keyboard_row in keyboard:
        inline_keyboard_row = []
        for keyboard_button in keyboard_row:
            if 'inline_kwargs' in keyboard_button:
                inline_keyboard_row.append(pyrogram.types.InlineKeyboardButton(keyboard_button['name'], **keyboard_button['inline_kwargs']))
                continue
            if 'button_class' in keyboard_button:
                button = keyboard_button['button_class'](controller, **keyboard_button.get('kwargs', {}))
            elif 'button' in keyboard_button:
                button = keyboard_button['button']
            else:
                raise ValueError('Neither button_class nor button specified')
            button.creation_date = dt
            button.callback_data = button.crc32 + uuid.uuid4().bytes
            db_buttons.append(button.row)
            inline_keyboard_row.append(pyrogram.types.InlineKeyboardButton(button.get_inline_button_name(keyboard_button['name']), callback_data=button.callback_data))
        inline_keyboard.append(inline_keyboard_row)
    db.add_all(db_buttons)
    await db.commit()
    return pyrogram.types.InlineKeyboardMarkup(inline_keyboard)


async def create_simple_keyboard(controller, keyboard, callback=None):
    for row in keyboard:
        for keyboard_button in row:
            if 'inline_kwargs' in keyboard_button or 'button' in keyboard_button:
                continue
            if 'button_class' not in keyboard_button:
                keyboard_button['button_class'] = SimpleButton
            if 'kwargs' not in keyboard_button:
                keyboard_button['kwargs'] = {}
            callback = keyboard_button.get('callback', None) or callback
            if callback:
                keyboard_button['kwargs']['callback_name'] = callback.__name__
    return await create_keyboard(controller, keyboard)


async def create_simple_check_box_keyboard(controller, keyboard, default_state=False):
    for row in keyboard:
        for keyboard_button in row:
            if 'inline_kwargs' in keyboard_button or 'button' in keyboard_button or ('button_class' in keyboard_button and not issubclass(keyboard_button['button_class'], CheckBoxButton)):
                continue
            if 'button_class' not in keyboard_button:
                keyboard_button['button_class'] = SimpleCheckBoxButton
            if 'kwargs' not in keyboard_button:
                keyboard_button['kwargs'] = {}
            if 'is_checked' not in keyboard_button['kwargs']:
                keyboard_button['kwargs']['is_checked'] = default_state
    return await create_keyboard(controller, keyboard)


class TGBotKeyboardMixin:

    @on_callback_query()
    async def handle_callback_query(self, callback_query):
        try:
            callback_data = callback_query.data
            if len(callback_data) != 20:
                raise ValueError
            button_class = CRC32_BUTTON_CLASSES_MAP.get(callback_data[:4])
            if not button_class:
                raise ValueError
            result_keyboard = []
            db_buttons = []
            button_classes_data_map = {}
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
                    button_class = CRC32_BUTTON_CLASSES_MAP[button.callback_data[:4]]
                    if button_class not in button_classes_data_map:
                        button_classes_data_map[button_class] = []
                    button_classes_data_map[button_class].append(button.callback_data)
                    if row_index is not None or button.callback_data != callback_query.data:
                        continue
                    row_index = current_row_index
                    column_index = current_column_index
                result_keyboard.append(result_row)
            if row_index is None:
                raise ValueError
            for button_class, buttons_data in button_classes_data_map.items():
                stmt = select(button_class.table).where(
                    button_class.table.callback_data.in_(buttons_data)
                )
                temp = (await db.execute(stmt)).scalars()
                db_buttons.extend([(button_class, b) for b in temp])
            if len(db_buttons) != buttons_with_callback_data:
                raise ValueError
            db_buttons.sort(key=lambda b: b[1].id)
            for current_row_index, row in enumerate(result_keyboard):
                for current_column_index, placeholder in enumerate(row):
                    if placeholder == 42:
                        button_class, db_button = db_buttons.pop(0)
                        result_keyboard[current_row_index][current_column_index] = button_class(self, db_button)
        except ValueError:
            await callback_query.answer('Извините, эта клавиатура устарела и больше не обслуживается. Пожалуйста, попробуйте воспользоваться клавиатурой из более позднего сообщения.', show_alert=True)
            return
        activated_button = result_keyboard[row_index][column_index]
        if activated_button.user_id != DEFAULT_USER_ID and callback_query.from_user.id != activated_button.user_id:
            await callback_query.answer('Извините, вы не можете активировать эту кнопку.', show_alert=True)
            return
        current_callback_query.set_context_var_value(callback_query)
        try:
            await activated_button.handle_button_activation(result_keyboard, row_index, column_index)
        except Exception:
            await callback_query.answer('Извините, что-то пошло не так.\nПожалуйста, попробуйте позже.', show_alert=True)
            raise
        if activated_button.answer:
            await callback_query.answer()
