import binascii
import uuid

import pyrogram
from pyrogram import filters
from sqlalchemy import delete, desc, or_, select

from tgbot.constants import DEFAULT_USER_ID
from tgbot.db import db, tables
from tgbot.group_manager import group_manager
from tgbot.gui.exceptions import (
    GUIError,
    NoWindowError,
    PermissionError,
    ReconstructionError,
)
from tgbot.handler_decorators import on_callback_query, on_message
from tgbot.helpers import ContextVarWrapper
from tgbot.users import current_user

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
        self.swap = False

    async def build(self, *args, **kwargs):
        self.row = tables.Window(chat_id=self.chat_id, user_id=self.user_id)
        self.row.window_class_crc32 = self.crc32
        self.current_tab = self.tabs[0](self)
        self.row.current_tab_index = 0
        db.add(self.row)
        await self.current_tab.build(*args, **kwargs)

    def schedule_swap(self):
        self.swap = True

    async def render(self):
        text, keyboard = await self.current_tab.render()
        if self.current_tab.input_fields:
            self.row.input_required = True
        else:
            self.row.input_required = False
        if self.swap and self.row.message_id:
            await self.controller.app.delete_messages(self.row.chat_id, self.row.message_id)
            self.row.message_id = None
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
    async def reconstruct(cls, controller, chat_id, window_id, message=None, row=None):
        if not row:
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
            message = await controller.app.get_messages(chat_id, row.message_id)
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
        await window.current_tab.reconstruct(message.text, buttons)
        return window

    async def handle_button_activation(self):
        await self.current_tab.handle_button_activation()

    async def process_input(self, text):
        await self.current_tab.process_input(text)

    async def switch_tab(self, new_tab, *args, save_current_tab=False, **kwargs):
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
        return self.current_tab


class BaseKeyboard:

    def __init__(self, tab):
        self.tab = tab
        self.buttons = []

    def add_row(self, *buttons):
        self.buttons.append(list(buttons))

    def add_button(self, button):
        if not self.buttons:
            self.add_row()
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
        for row in self.buttons:
            for i, button in enumerate(row):
                if isinstance(button, pyrogram.types.InlineKeyboardButton):
                    db_row = tables.PyrogramButton()
                    db_row.set_data(button)
                else:
                    db_row = tables.PyrogramButton(text=button.text, callback_data=button.row.callback_data)
                if i == len(row)-1:
                    db_row.right_button = True
                db_row.tab_index = self.tab.window.row.current_tab_index
                db_row.window_id = self.tab.window.row.id
                db.add(db_row)

    async def restore(self):
        stmt = select(tables.PyrogramButton).where(
            tables.PyrogramButton.window_id == self.tab.window.row.id,
            tables.PyrogramButton.tab_index == self.tab.row.index_in_window
        )
        db_buttons = (await db.execute(stmt)).scalars()
        buttons = [[]]
        for db_button in db_buttons:
            button = db_button.get_button()
            buttons[-1].append(button)
            if db_button.right_button:
                buttons.append([])
            await db.delete(db_button)
        await self.reconstruct(buttons)

    async def destroy(self):
        for row in self.buttons:
            for button in row:
                await button.destroy()


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
            self.row.window = self.keyboard.tab.window.row
        db.add(self.row)

    async def render(self):
        await self.db_render()
        return pyrogram.types.InlineKeyboardButton(self.text, callback_data=self.row.callback_data)

    async def destroy(self):
        await db.delete(self.row)


class InputField:

    def __init__(self, name, text=None, method_name=None):
        self.name = name
        self.text = text
        self.method_name = method_name or f'process_{name}'

    # Validation probably will be implemented here later


class BaseText:
    table = tables.Text

    def __init__(self, tab):
        self.tab = tab
        self.one_time_header = True

    async def build(self, *args, **kwargs):
        self.row = self.table(
            *args,
            window_id=self.tab.window.row.id,
            tab_id=self.tab.row.id,
            **kwargs
        )
        db.add(self.row)

    def set_header(self, header, one_time=True):
        self.row.header = header
        self.one_time_header = one_time

    def set_body(self, body):
        self.row.body = body

    def set_input_field_text(self, text):
        self.row.input_field_text = text

    async def render(self):
        text = ''
        if self.row.header:
            text += f'{self.row.header}\n{"-"*60}\n'
            if self.one_time_header:
                self.row.header = None
        body = []
        if self.row.body:
            body.append(self.row.body)
        if self.row.input_field_text:
            body.append(self.row.input_field_text)
        body = '\n'.join(body)
        if not body:
            body = '.'
        text += body
        return text.format(**await self.tab.get_text_data())

    async def reconstruct(self, text):
        # The initial text does not seem to be needed here, but let it be just in case
        stmt = select(self.table).where(
            self.table.window_id == self.tab.window.row.id,
            self.table.tab_id == self.tab.row.id,
        )
        self.row = (await db.execute(stmt)).scalar()
        if not self.row:
            raise ReconstructionError('Text not found')

    async def save(self):
        pass

    async def restore(self):
        await self.reconstruct(None)

    async def destroy(self):
        await db.delete(self.row)


class Text(BaseText):
    pass


class BaseTab:
    table = tables.Tab
    text_class = Text
    keyboard_class = SimpleKeyboard
    input_fields = []
    rerender_text = True

    def __init__(self, window):
        self.window = window
        self.message_text = None
        self.text = self.get_text()
        self.keyboard = self.get_keyboard()

    def get_text(self):
        return  self.text_class(self)

    async def get_text_data(self):
        return {}

    def get_keyboard(self):
        return self.keyboard_class(self)

    async def build(self, *args, **kwargs):
        self.row = self.table(*args, window=self.window.row, **kwargs)
        self.row.index_in_window = self.window.row.current_tab_index
        if self.input_fields:
            self.row.current_input_field_index = 0
        db.add(self.row)
        # In some places further window and tab identifiers will be needed.
        # Therefore, we need to insert the previously created window and tab to the database.
        await db.flush()
        await self.text.build()

    async def render(self):
        if self.rerender_text or not self.message_text:
            if self.input_fields and self.input_fields[self.row.current_input_field_index].text:
                self.text.set_input_field_text(self.input_fields[self.row.current_input_field_index].text)
            text = await self.text.render()
        else:
            text = self.message_text
        keyboard = await self.keyboard.render()
        return text, keyboard

    async def reconstruct(self, text, buttons):
        stmt = select(self.table).where(
            self.table.window_id == self.window.row.id,
            self.table.index_in_window == self.window.row.current_tab_index
        )
        self.row = (await db.execute(stmt)).scalar()
        if not self.row:
            raise ReconstructionError('Tab not found')
        self.message_text = text
        await self.text.reconstruct(text)
        await self.keyboard.reconstruct(buttons)

    async def handle_button_activation(self):
        await self.keyboard.handle_button_activation()

    async def process_input(self, text):
        callback = getattr(self, self.input_fields[self.row.current_input_field_index].method_name)
        await callback(text)

    def switch_input_field(self, field_name=None, previous=False, next=True):
        if field_name is not None:
            for i, field in enumerate(self.input_fields):
                if field.name == field_name:
                    self.row.current_input_field_index = i
                    return
            raise NameError(f'Field "{field_name}" not found')
        if previous == next:
            raise ValueError(f'Previous should not be equal to next')
        if previous:
            if self.row.current_input_field_index == 0:
                raise ValueError('This is the first input field')
            self.row.current_input_field_index -= 1
        else:
            if self.row.current_input_field_index == len(self.input_fields)-1:
                raise ValueError('This is the last input field')
            self.row.current_input_field_index += 1

    async def save(self):
        await self.text.save()
        await self.keyboard.save()

    async def restore(self):
        stmt = select(self.table).where(
            self.table.window_id == self.window.row.id,
            self.table.index_in_window == self.window.row.current_tab_index
        )
        row = (await db.execute(stmt)).scalar()
        if not row:
            return False
        self.row = row
        await self.text.restore()
        await self.keyboard.restore()
        return True

    async def destroy(self):
        await db.delete(self.row)
        await self.text.destroy()
        await self.keyboard.destroy()


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

    @on_message(filters.text, group=group_manager.PROCESS_INPUT)
    async def process_input(self, message):
        stmt = select(tables.Window).where(
            tables.Window.chat_id == message.chat.id,
            or_(tables.Window.user_id == DEFAULT_USER_ID, tables.Window.user_id == current_user.user_id),
            tables.Window.input_required == True
        ).order_by(
            desc(tables.Window.id)
        )
        window = (await db.execute(stmt)).scalar()
        if not window:
            message.continue_propagation()
        window_class = window_registry[window.window_class_crc32]
        window = await window_class.reconstruct(self, message.chat.id, window.id, row=window)
        await window.process_input(message.text)
        await window.render()
        await db.commit()
        message.stop_propagation()
