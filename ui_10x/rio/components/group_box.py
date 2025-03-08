import rio

class GroupBox(rio.Component):
    """
    A component that groups related controls with a labeled border.

    Attributes:
        title: The text displayed as the group's title.
        children: A list of child components to be grouped.
    """
    title: str
    children: list[rio.Component] = []

    def build(self) -> rio.Component:
        """
        Build the UI as a fieldset with a legend title and child components.
        """
        return rio.Stack(
            rio.Rectangle(
                fill=rio.Color.TRANSPARENT,
                stroke=rio.Stroke(color=rio.Color.GRAY, width=0.1),
                corner_radius=0.5,
            ),
            rio.Column(
                rio.Text(self.title, margin_bottom=-0.5),  # Title sits on the border
                rio.Column(*self.children, margin=1),       # Content inside
            ),
        )