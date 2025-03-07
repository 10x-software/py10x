import rio

class RadioButton(rio.Component):
    label: str
    value: str
    group: str
    selected_value: str  # Tracks the currently selected value in the group
    on_change: rio.EventHandler = None

    def build(self) -> rio.Component:
        return rio.Row(
            rio.Html(
                tag="input",
                attributes={
                    "type": "radio",
                    "name": self.group,
                    "value": self.value,
                    "checked": self.value == self.selected_value,
                    "onchange": lambda event: self.on_change(self.value),
                },
            ),
            rio.Text(self.label),
        )