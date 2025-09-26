import pytest
import rio.testing
from ui_10x.rio.component_builder import DynamicComponent
from ui_10x.rio.widgets import LineEdit


async def test_line_edit() -> None:
    widget = LineEdit('Hello')

    def build() -> rio.Component:
        return DynamicComponent(widget)

    async with rio.testing.DummyClient(build) as test_client:
        component = test_client.get_component(rio.TextInput)
        with pytest.raises(ValueError):
            test_client.get_component(rio.Tooltip)

        assert component.text == 'Hello'
        component.text = 'Goodbye'
        assert widget.text() == 'Goodbye'

        widget.set_text('Done')
        assert component.text == 'Done'

        component.text = 'Updated'
        widget.set_tool_tip('Tip')
        await test_client.wait_for_refresh()

        assert widget.text() == 'Updated'
        tip_component = test_client.get_component(rio.Tooltip)
        assert tip_component
        text_component = test_client.get_component(rio.Text)
        assert text_component.text == 'Tip'
