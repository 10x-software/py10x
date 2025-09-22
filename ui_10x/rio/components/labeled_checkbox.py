import rio


class LabeledCheckBox(rio.Component):
    label: str = ''
    is_on: bool = False
    on_change: rio.EventHandler[rio.CheckboxChangeEvent] = None

    def build(self):
        return rio.Row(rio.Text(self.label), rio.Checkbox(is_on=self.bind().is_on, on_change=self.on_change))
