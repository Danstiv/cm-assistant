from tgbot.gui import BaseKeyboard


class GridKeyboard(BaseKeyboard):

    def __init__(self, *args, width, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = width

    def add_button(self, button):
        if not self.buttons or len(self.buttons[-1]) == self.width:
            self.add_row()
        self.buttons[-1].append(button)
