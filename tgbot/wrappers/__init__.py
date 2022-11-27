import pyrogram
from pyrogram import enums

from tgbot.enums import QuoteReplyMode
from tgbot.wrappers.name_inflection import NameString, wrap_name_string
from tgbot.wrappers.dispatcher import Dispatcher


class User(pyrogram.types.User):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._full_username = None
        self._full_name = None

    @property
    def first_name(self):
        return self._first_name

    @first_name.setter
    def first_name(self, value):
        if not self._client.controller.username_inflection or not isinstance(value, str):
            self._first_name = value
            return
        self._first_name = wrap_name_string(value)

    @property
    def last_name(self):
        return self._last_name

    @last_name.setter
    def last_name(self, value):
        if not self._client.controller.username_inflection or not isinstance(value, str):
            self._last_name = value
            return
        self._last_name = wrap_name_string(value)

    @property
    def full_name(self):
        if self._full_name is not None:
            return self._full_name
        components = [self.first_name]
        if self.last_name:
            components.extend([' ', self.last_name])
        self._full_name = NameString(components) if self._client.controller.username_inflection else ''.join(components)
        return self._full_name

    @property
    def full_username(self):
        if self._full_username is not None:
            return self._full_username
        components = [self.full_name]
        if self.username:
            components.append(' @' + self.username)
        self._full_username = NameString(components) if self._client.controller.username_inflection else ''.join(components)
        return self._full_username

    @property
    def log_name(self):
        '''Name to use in logs'''
        components = []
        if self.username:
            components.append(self.username)
        components.append(str(self.id))
        return ' '.join(components)

    @property
    def gender(self):
        if not self._client.controller.username_inflection:
            raise AttributeError('Username inflection not enabled')
        return self.first_name.gender


class Message(pyrogram.types.Message):

    async def reply(self, *args, quote=None, reply_to_message_id=None, **kwargs):
        if quote is None:
            current_mode = self._client.controller.quote_reply_mode
            if current_mode == QuoteReplyMode.ON:
                quote = True
            elif current_mode == QuoteReplyMode.OFF:
                quote = False
            else:  # PYROGRAM mode
                quote = self.chat.type != enums.ChatType.PRIVATE
        if reply_to_message_id is None and quote:
            reply_to_message_id = self.id
        kwargs['chat_id'] = self.chat.id
        kwargs['reply_to_message_id'] = reply_to_message_id
        return await self._client.controller.send_message(*args, **kwargs)


def apply_wrappers():
    pyrogram.types.user_and_chats.user.User = User
    pyrogram.types.messages_and_media.message.Message = Message
    pyrogram.dispatcher.Dispatcher = Dispatcher
    pyrogram.client.Dispatcher = Dispatcher
