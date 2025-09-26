import rio


class LineEditComponent(rio.Component):
    text: str | None = None
    tooltip: str | None = None
    is_sensitive: bool = True
    on_change: rio.EventHandler[[str]] = None
    on_lose_focus: rio.EventHandler[[str]] = None
    text_style: rio.TextStyle | None = None

    def build(self):
        text_input = rio.TextInput(
            self.bind().text,
            is_sensitive=self.is_sensitive,
            on_change=self.on_change,
            on_lose_focus=self.on_lose_focus,
            text_style=self.text_style,
        )

        if self.tooltip is None:
            return text_input

        tooltip = rio.Tooltip(text_input, self.tooltip)
        return rio.Stack(tooltip, text_input)
