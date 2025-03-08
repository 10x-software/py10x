import rio

class Separator(rio.Component):
    """
    A component that draws a horizontal or vertical line to separate UI sections.

    Attributes:
        orientation: "horizontal" or "vertical" to define the separator's direction.
        thickness: The width of the line in Rio units (default: 0.1).
        color: The color of the line (default: gray).
    """
    orientation: str = "horizontal"  # "horizontal" or "vertical"
    thickness: float = 0.1
    color: rio.Color = rio.Color.GRAY

    def build(self) -> rio.Component:
        """
        Build the UI as an <hr> for horizontal or a styled <div> for vertical.
        """
        if self.orientation == "horizontal":
            return rio.Rectangle(
                min_height=self.thickness,
                fill=self.color,
                margin_vertical=0.5,
            )
        else:
            return rio.Rectangle(
                min_width=self.thickness,
                fill=self.color,
                margin_horizontal=0.5,
            )

    def __post_init__(self) -> None:
        """
        Validate the orientation attribute.
        """
        if self.orientation not in ("horizontal", "vertical"):
            raise ValueError(f"Orientation must be 'horizontal' or 'vertical' (got {self.orientation!r})")