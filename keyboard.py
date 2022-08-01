import tables
from tgbot.keyboard import Button, button_decorator


@button_decorator
class GroupUserButton(Button):
    table = tables.GroupUserButton
