import rio

class RadioButton(rio.Component):
    label: str
    value: str
    selected_value: bool
    on_select: rio.EventHandler = None

    def build(self) -> rio.Component:
        # Use an icon to visually represent the radio button state
        icon_name = "circle" if self.selected_value != self.value else "circle-filled"
        return rio.Row(
                rio.IconButton(
                    icon_name,
                    on_press=lambda: self.on_select(self.value)
                ),
                rio.Text(self.label),
                spacing=0.5,  # Space between icon and label
        )