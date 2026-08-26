from __future__ import annotations

import rio


class RadioButton(rio.Component):
    label: str = ''
    value: str = ''
    checked: bool = False
    on_select: rio.EventHandler[[]] = None

    def icon_name(self) -> str:
        return f'radio_button_{"checked" if self.checked else "unchecked"}'

    def _on_press(self, _event: rio.PointerEvent = None) -> None:
        if self.on_select:
            self.on_select()
        else:
            self.checked = True

    def build(self) -> rio.Component:
        # Whole row must be pressable — label-only clicks were ignored before.
        return rio.PointerEventListener(
            content=rio.Row(
                rio.Icon(self.icon_name(), min_width=1.25, min_height=1.25),
                rio.Text(self.label),
                spacing=0.5,
                align_y=0.5,
            ),
            on_press=self._on_press,
        )
