from tgbot.gui.tabs import Tab
from tgbot.gui.keyboards import GridKeyboard
from tgbot.gui.buttons import SimpleButton


class GroupSelectionTabMixin(Tab):

    def get_keyboard(self):
        return GridKeyboard(self, width=1)

    async def set_groups(self, groups, callback):
        for group in groups:
            group_title = (await self.window.controller.app.get_chat(group.group_id)).title
            self.keyboard.add_button(SimpleButton(
                group_title,
                arg=group.id,
                callback=callback
            ))
