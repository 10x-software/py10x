import rio
from ui_10x.rio.components.radio_button import RadioButton


class RadioButtons(rio.Component):
    """
    A component that displays a group of radio buttons for single-option selection.

    Attributes:
        options: A list of tuples, each containing (label, value) for an option.
        selected_value: The currently selected option's value.
        on_change: Optional callback triggered when the selection changes.
    """
    options: list[tuple[str, str]]  # [(label, value), ...]
    selected_value: str
    on_change: rio.EventHandler = None

    def build(self) -> rio.Component:
        """
        Build the UI as a column of RadioButton components.
        """
        # Create a list of RadioButton components
        radio_buttons = [
            RadioButton(
                label=label,
                value=value,
                selected_value=self.selected_value,
                on_change=self._handle_change,
            )
            for label, value in self.options
        ]

        # Arrange them in a column
        return rio.Column(
            *radio_buttons,
            spacing=1,
            align_x=0,  # Left-align by default
        )

    async def _handle_change(self, new_value: str) -> None:
        """
        Handle the radio button change event.
        """
        # Update the selected value
        self.selected_value = new_value

        # Trigger the on_change callback if provided
        if self.on_change:
            await self.on_change(new_value)