import pyrogram

from tgbot.wrappers.dispatcher import Dispatcher


class User(pyrogram.types.User):

    @property
    def full_name(self):
        username_components = [self.first_name]
        if self.last_name:
            username_components.append(self.last_name)
        if self.username:
            username_components.append('@' + self.username)
        return ' '.join(username_components)

    @property
    def log_name(self):
        '''Name to use in logs'''
        username_components = []
        if self.username:
            username_components.append(self.username)
        username_components.append(str(self.id))
        return ' '.join(username_components)


def apply_wrappers():
    pyrogram.types.user_and_chats.user.User = User
    pyrogram.dispatcher.Dispatcher = Dispatcher
    pyrogram.client.Dispatcher = Dispatcher
