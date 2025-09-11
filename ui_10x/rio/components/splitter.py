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
    direction: t.Literal['horizontal','vertical'] = 'vertical'
    handle_size: float = 0.5  # Width of the splitter handle
    min_size_percent: float = 10.0  # Minimum width for each child (%)
    child_proportions: t.Sequence[float] = None
    _component_width: float = 0.0
    _component_height: float = 0.0

    def __init__(self, *children,
             direction: t.Literal['horizontal','vertical'] = 'vertical',
             handle_size:float=0.5,
             min_size_percent:float=10.0,
             child_proportions: t.Literal["homogeneous"] | t.Sequence[float] = "homogeneous",
            **kwargs
         ):
        super().__init__(**kwargs)
        self.direction = direction
        self.children = list(children)
        self.handle_size = handle_size
        self.min_size_percent = min_size_percent
        if not isinstance(child_proportions,(list,tuple)):
            num_children = len(children)
            self.child_proportions = [1.0] * num_children if num_children else []
        else:
            assert len(child_proportions) == len(children)
            assert all(p>=0 for p in child_proportions), "Proportions must be non-negative"
            self.child_proportions = list(child_proportions)

    def on_drag(self, index: int, event: rio.PointerMoveEvent) -> None:
        """
        Handle drag events on the splitter at the given index.
        Adjusts the proportions of the two adjacent children.
        """
        horizontal = self.direction == 'horizontal'
        total_size =  self._component_width if horizontal else self._component_height

        # Convert drag movement to a proportion change
        total_proportion = sum(self.child_proportions)
        relative_size = event.relative_x if horizontal else event.relative_y
        delta_proportion = (relative_size / total_size) * total_proportion

        # Adjust the proportions of the left and right children
        prev_index = index
        next_index = index + 1

        # Calculate current sizes as percentages to check minimum constraints
        current_sizes = [(p / total_proportion * 100.0) for p in self.child_proportions]
        new_left_size = current_sizes[prev_index] + (delta_proportion / total_proportion * 100.0)
        new_right_size = current_sizes[next_index] - (delta_proportion / total_proportion * 100.0)

        # Check minimum size constraints
        if new_left_size >= self.min_size_percent and new_right_size >= self.min_size_percent:
            self.child_proportions[prev_index] += delta_proportion
            self.child_proportions[next_index] -= delta_proportion
            # Ensure proportions don't go negative
            self.child_proportions[prev_index] = max(0.0, self.child_proportions[prev_index])
            self.child_proportions[next_index] = max(0.0, self.child_proportions[next_index])
            child_sizes = [p / total_proportion * total_size for p in self.child_proportions]
            print( f'{child_sizes=}, total_size={total_size} ({sum(child_sizes):.2f})' )

        self.child_proportions = self.child_proportions # force refresh

    def build(self) -> rio.Component:
        # If no children, return an empty component
        if not self.children:
            return rio.Rectangle()

        # Build the layout with children and splitters
        components = []
        horizontal = self.direction == 'horizontal'
        for i, child in enumerate(self.children):
            # Wrap child in ScrollArea
            scrollable_content = rio.ScrollContainer(
                content=child,
                # scroll_x='never' if horizontal else 'auto',
                # scroll_y='auto' if horizontal else 'never',
            )
            # Create the pane
            pane = rio.Rectangle(
                content=scrollable_content,
                **{"grow_x" if horizontal else "grow_y": True},  # Stretch to fill proportional space
                fill=rio.Color.from_hex("#87ceeb") if i % 2 == 0 else rio.Color.from_hex("#90ee90"),
                margin=1,  # Spacing around the child content
            )
            # Add a splitter handle to the right of all but the last pane
            if i < len(self.children) - 1:
                splitter = rio.PointerEventListener(
                    content=rio.Rectangle(
                        **{"grow_x" if horizontal else "grow_y": False,
                           "min_width" if horizontal else "min_height" : self.handle_size},
                        fill=rio.Color.from_hex("#808080"),
                        cursor="move",  # Valid CursorStyle for dragging
                    ),
                    on_drag_move=lambda event, idx=i: self.on_drag(idx, event),
                    **{
                        "align_x" if horizontal else "align_y": 1.0,  # Position at the right edge
                        "margin_right" if horizontal else "margin_bottom": -self.handle_size / 2,  # Extend slightly into the next pane
                    }
                )
                # Combine pane and splitter in a Stack
                components.append(
                    rio.Stack(
                        pane,
                        splitter,
                        **{"grow_x" if horizontal else "grow_y": True},  # Ensure the Stack follows the proportion
                    )
                )
            else:
                # Last pane has no splitter
                components.append(pane)

        container = rio.Row if self.direction=='horizontal' else rio.Column
        return rio.SizeObserver(
            container(
                *components,
                spacing=0,
                proportions=self.bind().child_proportions,  # Dynamically control pane sizes
            ),
            on_resize=self._on_resize,
        )

    def _on_resize(self, event: rio.SizeEvent) -> None:
        print(event, self.session.window_width, self.session.window_height)
        self._component_width = event.component_width
        self._component_height = event.component_height
