from tgbot.gui import BaseButton


class ButtonWithCallback(BaseButton):
    def __init__(self, *args, callback=None, **kwargs):
        if callback is not None:
            kwargs['callback_name'] = callback.__name__
        super().__init__(*args, **kwargs)

    @property
    def callback(self):
        return getattr(self.keyboard.tab, self.row.callback_name)
