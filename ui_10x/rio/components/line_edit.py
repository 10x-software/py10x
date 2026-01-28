from __future__ import annotations

import rio


class LineEditComponent(rio.Component):
    text: str | None = None
    tooltip: str | None = None
    is_sensitive: bool = True
    on_change: rio.EventHandler[[str]] = None
    on_lose_focus: rio.EventHandler[[str]] = None
    text_style: rio.TextStyle | None = None
    is_secret: bool = False
    on_pointer_up: rio.EventHandler[[rio.PointerEvent]] = None

    def build(self):
        component = rio.TextInput(
            self.bind().text,
            is_sensitive=self.is_sensitive,
            on_change=self.on_change,
            on_lose_focus=self.on_lose_focus,
            text_style=self.text_style,
            is_secret=self.is_secret,
        )

        if self.on_pointer_up is not None:
            component = rio.PointerEventListener(
                component,
                on_pointer_up=self.on_pointer_up,
                consume_events=False,
                event_order='before-child',
            )

        if self.tooltip is not None:
            component = rio.Tooltip(anchor=component, tip=self.tooltip)

        return component
