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
        return rio.Html(
            tag="fieldset",
            children=[
                rio.Html(
                    tag="legend",
                    children=[rio.Text(self.title)],
                ),
                rio.Column(
                    *self.children,
                    spacing=1,
                    margin=1,  # Adds padding inside the fieldset
                ),
            ],
            # Optional: Apply Material Design styling via Rio's style system
            style=rio.BoxStyle(
                border=rio.Border.all(
                    width=0.1,
                    color=rio.Color.GRAY,
                ),
                border_radius=0.5,
            ),
        )