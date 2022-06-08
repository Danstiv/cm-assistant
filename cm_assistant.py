import asyncio
import os

from pyrogram import filters

from tgbot import BotController
from tgbot.handler_decorators import on_message


class Controller(BotController):
    def __init__(self):
        super().__init__(bot_name='cm_assistant')
        self.chat_id = int(os.environ['CHAT_ID'])

    def get_global_filter(self):
        return filters.text & filters.chat(self.chat_id)

    def get_default_chat_id(self):
        return self.chat_id

    @on_message()
    async def test_handler(self, message):
        keyboard = await self.create_keyboard([[[
            'test',
            self.test_keyboard_callback
        ]]])
        await message.reply('working', reply_markup=keyboard)

    async def test_keyboard_callback(self, callback_query, db_button):
        await self.send_message(f'Button {db_button.id} is working')


if __name__ == '__main__':
    controller = Controller()
    asyncio.run(controller.start())
