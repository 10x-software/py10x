import rio


class GroupBox(rio.Component):
    """
    A component that groups related controls with a labeled border.

    Attributes:
        title: The text displayed as the group's title.
        children: A list of child components to be grouped.
    """

    children: list[rio.Component] = []
    title: str = ''

    def build(self) -> rio.Component:
        """
        Build the UI as a bordered box with an optional title above the content.

        Avoids negative title margins (those clipped the heading under parent overflow).
        """
        content = rio.Column(*self.children, margin=0.8)
        framed = rio.Rectangle(
            content=content,
            fill=rio.Color.TRANSPARENT,
            stroke_width=0.1,
            stroke_color=rio.Color.GRAY,
            corner_radius=0.5,
        )
        if not self.title:
            return framed
        return rio.Column(
            rio.Text(self.title, margin_left=0.3, margin_bottom=0.2),
            framed,
            spacing=0,
        )
