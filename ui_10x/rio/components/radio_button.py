from __future__ import annotations

from functools import partial

import rio


class RadioButton(rio.Component):
    label: str = ''
    value: str = ''
    selected_value: bool = False
    on_select: rio.EventHandler[str] = None

    async def on_press(self, button) -> None:
        if self.on_select:
            self.on_select(self.value)
        button.icon = self.icon_name()

    def icon_name(self) -> str:
        return f"radio_button_{'checked' if self.selected_value == self.value else 'unchecked'}"

    def build(self) -> rio.Component:
        # Use an icon to visually represent the radio button state
        icon_button = rio.IconButton(self.icon_name())
        icon_button.on_press = partial(self.on_press, icon_button)
        return rio.Row(
                icon_button,
                rio.Text(self.label),
                spacing=0.5,  # Space between icon and label
        )