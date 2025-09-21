import typing

import rio


class Separator(rio.Component):
    """
    A component that draws a horizontal or vertical line to separate UI sections.

    Attributes:
        orientation: "horizontal" or "vertical" to define the separator's direction.
        thickness: The width of the line in Rio units (default: 0.1).
        color: The color of the line (default: gray).
    """

    orientation: typing.Literal['horizontal', 'vertical'] = 'horizontal'
    thickness: float = 0.1
    color: rio.Color = rio.Color.GRAY

    def build(self) -> rio.Component:
        if self.orientation == 'horizontal':
            return rio.Rectangle(min_height=self.thickness, fill=self.color, margin_y=0.5, grow_y=False, align_y=0.5)
        else:
            return rio.Rectangle(min_width=self.thickness, fill=self.color, margin_x=0.5, grow_x=False, align_x=0.5)
