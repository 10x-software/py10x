from __future__ import annotations

import rio
import typing as t

class Splitter(rio.Component):
    """
    A custom Rio component that arranges children horizontally like a Row,
    with draggable splitters between them for resizing.
    """
    # Props
    children: list[rio.Component] = []
    handle_width: float = 0.5  # Width of the splitter handle
    min_width_percent: float = 10.0  # Minimum width for each child (%)
    child_proportions: t.Literal["homogeneous"] | t.Sequence[float] | None = "homogeneous"

    def __init__(self, *children,
             handle_width:float=0.5,
             min_width_percent:float=10.0,
             child_proportions: t.Literal["homogeneous"] | t.Sequence[float] | None = "homogeneous",
            **kwargs
         ):
        super().__init__(**kwargs)
        self.children = list(children)
        self.handle_width = handle_width
        self.min_width_percent = min_width_percent
        if not isinstance(child_proportions,(list,tuple)):
            num_children = len(self.children)
            self.child_proportions = [1.0] * num_children if num_children else []
        else:
            assert len(child_proportions) == len(self.children)
            assert all(p>=0 for p in self.child_proportions), "Proportions must be non-negative"
            self.child_proportions = list(child_proportions)

    def on_drag(self, index: int, event: rio.PointerMoveEvent) -> None:
        """
        Handle drag events on the splitter at the given index.
        Adjusts the proportions of the two adjacent children.
        """
        total_width = self.session.window_width  # Window width in pixels
        total_proportion = sum(self.child_proportions)

        # Convert drag movement to a proportion change
        delta_proportion = (event.relative_x / total_width) * total_proportion

        # Adjust the proportions of the left and right children
        left_index = index
        right_index = index + 1

        # Calculate current widths as percentages to check minimum constraints
        current_widths = [(p / total_proportion * 100.0) for p in self.child_proportions]
        new_left_width = current_widths[left_index] + (delta_proportion / total_proportion * 100.0)
        new_right_width = current_widths[right_index] - (delta_proportion / total_proportion * 100.0)

        # Check minimum width constraints
        if new_left_width >= self.min_width_percent and new_right_width >= self.min_width_percent:
            self.child_proportions[left_index] += delta_proportion
            self.child_proportions[right_index] -= delta_proportion
            # Ensure proportions don't go negative
            self.child_proportions[left_index] = max(0.0, self.child_proportions[left_index])
            self.child_proportions[right_index] = max(0.0, self.child_proportions[right_index])

        self.child_proportions = self.child_proportions # force refresh

    def build(self) -> rio.Component:
        # If no children, return an empty component
        if not self.children:
            return rio.Rectangle()

        # Build the layout with children and splitters
        components = []
        for i, child in enumerate(self.children):
            # Create the pane
            pane = rio.Rectangle(
                content=child,
                grow_x=True,  # Stretch to fill proportional space
                fill=rio.Color.from_hex("#87ceeb") if i % 2 == 0 else rio.Color.from_hex("#90ee90"),
                margin=1,  # Spacing around the child content
            )
            # Add a splitter handle to the right of all but the last pane
            if i < len(self.children) - 1:
                splitter = rio.PointerEventListener(
                    content=rio.Rectangle(
                        min_width=self.handle_width,
                        grow_x=False,
                        fill=rio.Color.from_hex("#808080"),
                        cursor="move",  # Valid CursorStyle for dragging
                    ),
                    on_drag_move=lambda event, idx=i: self.on_drag(idx, event),
                    align_x=1.0,  # Position at the right edge
                    margin_right=-self.handle_width / 2,  # Extend slightly into the next pane
                )
                # Combine pane and splitter in a Stack
                components.append(
                    rio.Stack(
                        pane,
                        splitter,
                        grow_x=True,  # Ensure the Stack follows the proportion
                    )
                )
            else:
                # Last pane has no splitter
                components.append(pane)

        return rio.Row(
            *components,
            handle_width=0,
            grow_x=True,  # Expand to fill available width
            grow_y=True,  # Expand to fill available height
            proportions=self.bind().child_proportions,  # Dynamically control pane widths
        )
