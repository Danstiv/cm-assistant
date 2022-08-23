import binascii
import uuid

import pyrogram
from sqlalchemy import delete, or_, select

from tgbot.constants import DEFAULT_USER_ID
from tgbot.db import db, tables
from tgbot.group_manager import group_manager
from tgbot.gui.exceptions import (
    GUIError,
    NoWindowError,
    PermissionError,
    ReconstructionError,
)
from tgbot.handler_decorators import on_callback_query
from tgbot.helpers import ContextVarWrapper

current_callback_query = ContextVarWrapper('current_callback_query')
CALLBACK_QUERY_SIGNATURE = chr(128021).encode()
window_registry = {}
button_registry = {}


class RegistryMeta(type):

    def __new__(cls, name, bases, dct):
        if not bases:  # Base window class
            return super().__new__(cls, name, bases, dct)
        crc32 = binascii.crc32(name.encode())
        crc32 = crc32.to_bytes(4, 'big')
        if crc32 in cls.registry:
            if cls.registry[crc32].__name__ == name:
                raise ValueError(f'Class {name} already registered')
            raise ValueError(f'CRC32 for classes {cls.registry[crc32].__name__} and {name} matched!')
        dct['crc32'] = crc32
        instance = super().__new__(cls, name, bases, dct)
        cls.registry[crc32] = instance
        return instance


class WindowMeta(RegistryMeta):
    registry = window_registry


class ButtonMeta(RegistryMeta):
    registry = button_registry


class Window(metaclass=WindowMeta):
    def __init__(self, controller, chat_id, user_id=None):
        self.controller = controller
        self.chat_id = chat_id
        self.user_id = user_id

    async def build(self, *args, **kwargs):
        self.row = tables.Window(chat_id=self.chat_id, user_id=self.user_id)
        self.current_tab = self.tabs[0](self)
        self.row.current_tab_index = 0
        db.add(self.row)
        await db.flush()
        await self.current_tab.build(*args, **kwargs)

    async def render(self):
        text, keyboard = await self.current_tab.render()
        if not self.row.message_id:
            message = await self.controller.send_message(text, self.row.chat_id, reply_markup=keyboard, blocking=True)
            self.row.message_id = message.id
            db.add(self.row)
        else:
            try:
                await self.controller.app.edit_message_text(self.row.chat_id, self.row.message_id, text, reply_markup=keyboard)
            except pyrogram.errors.MessageNotModified:
                pass

    @classmethod
    async def reconstruct(cls, controller, chat_id, window_id, message=None):
        stmt = select(tables.Window).where(
            tables.Window.id==window_id,
            tables.Window.chat_id==chat_id,
        )
        row = (await db.execute(stmt)).scalar()
        if row is None:
            raise NoWindowError
        if row.user_id != DEFAULT_USER_ID and row.user_id != current_user.user_id:
            raise PermissionError
        if message is None:
            message = await controller.app.get_messages(chat_id, window.row.message_id)
            # "A message can be empty in case it was deleted or you tried to retrieve a message that doesn’t exist yet."
            if message.empty:
                await db.delete(row)
                raise NoWindowError('Message not found')
        buttons = []
        if isinstance(message.reply_markup, pyrogram.types.InlineKeyboardMarkup):
            buttons = message.reply_markup.inline_keyboard
        window = cls(controller, row.chat_id, row.user_id)
        window.row = row
        window.current_tab = window.tabs[row.current_tab_index](window)
        await window.current_tab.reconstruct(buttons)
        return window

    async def handle_button_activation(self):
        await self.current_tab.handle_button_activation()

    async def switch_tab(self, new_tab, *args, save_current_tab=True, **kwargs):
        try:
            new_tab_index = self.tabs.index(new_tab)
        except ValueError:
            raise GUIError('Requested tab not found')
        if not save_current_tab:
            await self.current_tab.destroy()
        else:
            await self.current_tab.save()
        self.row.current_tab_index = new_tab_index
        self.current_tab = new_tab(self)
        restored = await self.current_tab.restore()
        if not restored:
            await self.current_tab.build(*args, **kwargs)


class BaseKeyboard:

    def __init__(self, tab):
        self.tab = tab
        self.buttons = []

    def add_button(self, button):
        if not self.buttons:
            self.buttons.append([])
        self.buttons[-1].append(button)

    async def render(self):
        keyboard = []
        for row in self.buttons:
            keyboard.append([])
            for button in row:
                if isinstance(button, pyrogram.types.InlineKeyboardButton):
                    keyboard[-1].append(button)
                    continue
                if not isinstance(button, BaseButton):
                    raise ValueError(f'Button {button} is not a subclass of BaseButton')
                button.keyboard = self
                keyboard[-1].append(await button.render())
        return None if not keyboard else pyrogram.types.InlineKeyboardMarkup(keyboard)

    async def reconstruct(self, buttons):
        button_classes_data_map = {}
        db_buttons_count = 0
        callback_data_position_map = {}
        for row_index, row in enumerate(buttons):
            self.buttons.append([])
            for column_index, button in enumerate(row):
                if not button.callback_data:
                    self.buttons[-1].append(button)
                    continue
                button_class = button_registry.get(button.callback_data[12:16], None)
                if not button_class:
                    raise ReconstructionError('Button class not found')
                if button_class not in button_classes_data_map:
                    button_classes_data_map[button_class] = []
                button_classes_data_map[button_class].append(button.callback_data)
                db_buttons_count += 1
                self.buttons[-1].append(button.text)
                callback_data_position_map[button.callback_data] = (row_index, column_index)
        buttons_data = []
        for button_class, buttons_callback_data in button_classes_data_map.items():
            stmt = select(button_class.table).where(
                button_class.table.callback_data.in_(buttons_callback_data)
            )
            temp = (await db.execute(stmt)).scalars()
            buttons_data.extend([{'class': button_class, 'row': b} for b in temp])
        if len(buttons_data) != db_buttons_count:
            raise ReconstructionError(f'{len(buttons_data)} buttons out of {db_buttons_count} were fetched')
        for button_data in buttons_data:
            row_index, column_index = callback_data_position_map[button_data['row'].callback_data]
            text = self.buttons[row_index][column_index]
            button = button_data['class'](text, row=button_data['row'])
            button.keyboard = self
            self.buttons[row_index][column_index] = button

    async def handle_button_activation(self):
        for row_index, row in enumerate(self.buttons):
            for column_index, button in enumerate(row):
                if button.row.callback_data == current_callback_query.data:
                    await button.handle_button_activation(row_index, column_index)
                    return

    async def save(self):
        tab_index = self.tab.window.row.current_tab_index
        for row in self.buttons:
            for i, button in enumerate(row):
                if isinstance(button, pyrogram.types.InlineKeyboardButton):
                    data = json.loads(str(button))
                    del data['_']
                    db_row = tables.PyrogramButton(**data)
                else:
                    db_row = tables.PyrogramButton(text=button.text, callback_data=button.row.callback_data)
                if i == len(row)-1:
                    db_row.right_button = True
                db_row.tab_index = tab_index
                db_row.window_id = self.tab.window.row.id
                db.add(db_row)

    async def destroy(self):
        for row in self.buttons:
            for button in row:
                await button.destroy()

    async def restore(self):
        stmt = select(tables.PyrogramButton).where(
            tables.PyrogramButton.window_id == self.tab.window.row.id,
            tables.PyrogramButton.tab_index == self.tab.row.index_in_window
        )
        db_buttons = (await db.execute(stmt)).scalars()
        buttons = [[]]
        for db_button in db_buttons:
            raise NotImplementedError
            buttons[-1].append(button)
            if db_button.right_button:
                buttons.append([])
            await db.delete(db_button)
        await self.reconstruct(buttons)


class SimpleKeyboard(BaseKeyboard):
    pass


class BaseButton(metaclass=ButtonMeta):

    def __init__(self, text=None, *args, row=None, **kwargs):
        self.text = text
        self.row = row if row else self.table(*args, **kwargs)

    def set_text(self, text):
        self.text = text

    async def handle_button_activation(self, row_index, column_index):
        raise NotImplementedError

    async def db_render(self):
        if self.row.id is None:
            self.row.callback_data = CALLBACK_QUERY_SIGNATURE + self.keyboard.tab.window.crc32 + self.keyboard.tab.window.row.id.to_bytes(4, 'big') + self.crc32 + uuid.uuid4().bytes
            self.row.window_id = self.keyboard.tab.window.row.id
        db.add(self.row)

    async def render(self):
        await self.db_render()
        return pyrogram.types.InlineKeyboardButton(self.text, callback_data=self.row.callback_data)

    async def destroy(self):
        await db.delete(self.row)


class ButtonWithCallback(BaseButton):
    def __init__(self, *args, callback=None, **kwargs):
        if callback is not None:
            kwargs['callback_name'] = callback.__name__
        super().__init__(*args, **kwargs)

    @property
    def callback(self):
        return getattr(self.keyboard.tab, self.row.callback_name)


class SimpleButton(ButtonWithCallback):
    table = tables.SimpleButton

    async def handle_button_activation(self, row_index, column_index):
        await self.callback(self.row.arg)


class CheckBoxButton(ButtonWithCallback):
    table = tables.CheckBoxButton

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'row' not in kwargs:  # Creation
            self.row.text = self.text
        else:  # Reconstruction
            self.text = self.row.text

    def get_column_value_or_default(self, name):
        value = getattr(self.row, name)
        if value is not None:
            return value
        return self.row.__table__.c[name].default.arg

    async def render(self):
        await self.db_render()
        prefix = self.get_column_value_or_default('is_unchecked_prefix')
        if self.row.is_checked:
            prefix = self.get_column_value_or_default('is_checked_prefix')
        return pyrogram.types.InlineKeyboardButton(prefix + self.text, callback_data=self.row.callback_data)

    async def handle_button_activation(self, row_index, column_index):
        self.row.is_checked = not self.row.is_checked
        await self.callback(self.row.is_checked, self.row.arg)


class BaseTab:
    table = tables.Tab
    text = None
    keyboard_class = SimpleKeyboard

    def __init__(self, window):
        self.window = window
        self.keyboard = self.keyboard_class(self)

    def set_text(self, text):
        self.row.text = text

    async def build(self, *args, **kwargs):
        self.row = self.table(*args, window=self.window.row, **kwargs)
        self.row.index_in_window = self.window.row.current_tab_index
        if self.text is not None:
            self.row.text = self.text
        db.add(self.row)

    async def get_text_data(self):
        return {}

    async def render(self):
        text = self.row.text.format(**await self.get_text_data())
        keyboard = await self.keyboard.render()
        return text, keyboard

    async def reconstruct(self, buttons):
        stmt = select(self.table).where(
            self.table.window_id == self.window.row.id,
            self.table.index_in_window == self.window.row.current_tab_index
        )
        self.row = (await db.execute(stmt)).scalar()
        if not self.row:
            raise ReconstructionError('Tab not found')
        await self.keyboard.reconstruct(buttons)

    async def handle_button_activation(self):
        await self.keyboard.handle_button_activation()

    async def save(self):
        await self.keyboard.save()

    async def destroy(self):
        await db.delete(self.row)
        await self.keyboard.destroy()

    async def restore(self):
        stmt = select(self.table).where(
            self.table.window_id == self.window.row.id,
            self.table.index_in_window == self.window.row.current_tab_index
        )
        row = (await db.execute(stmt)).scalar()
        if not row:
            return False
        self.row = row
        await self.keyboard.restore()
        return True


class TGBotGUIMixin:

    @on_callback_query(group=group_manager.SET_CALLBACK_QUERY_CONTEXT)
    async def handle_callback_query(self, callback_query):
        current_callback_query.set_context_var_value(callback_query)
        if callback_query.data[:4] != CALLBACK_QUERY_SIGNATURE:
            callback_query.continue_propagation()
        try:
            window_cls = window_registry.get(callback_query.data[4:8], None)
            if not window_cls:
                raise NoWindowError
            window_id = int.from_bytes(callback_query.data[8:12], 'big')
            window = await window_cls.reconstruct(
                self,
                chat_id=callback_query.message.chat.id,
                window_id=window_id,
                message=callback_query.message
            )
            await window.handle_button_activation()
            await window.render()
            await callback_query.answer()
            await db.commit()
        except PermissionError:
            await callback_query.answer('Извините, вы не можете активировать эту кнопку.', show_alert=True)
        except ReconstructionError:
            await callback_query.answer('Извините, эта клавиатура устарела и больше не обслуживается. Пожалуйста, попробуйте воспользоваться клавиатурой из более позднего сообщения.', show_alert=True)
        except Exception:
            await callback_query.answer('Извините, что-то пошло не так.\nПожалуйста, попробуйте позже.', show_alert=True)
            self.log.exception(f'Необработанное исключение при обработке callback query:')
        finally:
            current_callback_query.reset_context_var()
            callback_query.stop_propagation()

    @on_callback_query(group=group_manager.RESET_CALLBACK_QUERY_CONTEXT)
    def callback_query_reset_handler(self, callback_query):
        current_callback_query.reset_context_var()
