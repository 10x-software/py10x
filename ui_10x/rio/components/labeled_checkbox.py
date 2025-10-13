import rio


class LabeledCheckBox(rio.Component):
    label: str = ''
    is_on: bool = False
    is_sensitive: bool = True
    on_change: rio.EventHandler[rio.CheckboxChangeEvent] = None

    def build(self):
        return rio.Row(
            rio.Text(self.label),
            rio.Checkbox(
                is_on=self.bind().is_on,
                is_sensitive=self.is_sensitive,
                on_change=self.on_change,
            ),
        )
