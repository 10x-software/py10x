from __future__ import annotations

import typing as t

import rio


class Splitter(rio.Component):
    """
    A custom Rio component that arranges children horizontally like a Row,
    or vertically as a column with draggable splitters between them for resizing.
    """

    # Props
    children: list[rio.Component] = []
    direction: t.Literal['horizontal', 'vertical'] = 'vertical'
    handle_size: float = 0.25  # Width of the *visible* splitter bar
    # 0.25rem (≈4px) is too thin to grab, and the listener only watches its child's box.
    handle_hit_size: float = 0.75
    min_size_percent: float = 10.0  # Minimum width for each child (%)
    child_proportions: t.Literal['homogeneous'] | t.Sequence[float] = 'homogeneous'
    _component_width: float = 0.0
    _component_height: float = 0.0

    def __post_init__(self):
        if not isinstance(self.child_proportions, (list, tuple)):
            num_children = len(self.children)
            self.child_proportions = [1.0] * num_children if num_children else []
        else:
            assert len(self.child_proportions) == len(self.children)
            assert all(p >= 0 for p in self.child_proportions), 'Proportions must be non-negative'
            self.child_proportions = list(self.child_proportions)

    def on_drag(self, index: int, event: rio.PointerMoveEvent) -> None:
        """
        Handle drag events on the splitter at the given index.
        Adjusts the proportions of the two adjacent children.
        """
        horizontal = self.direction == 'horizontal'
        total_size = self._component_width if horizontal else self._component_height

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

        self.child_proportions = self.child_proportions  # force refresh

    def build(self) -> rio.Component:
        if not self.children:
            return rio.Rectangle()

        # Panes and handles are plain siblings with explicit sizes, not Stack-wrapped children
        # under the container's `proportions=`: a Stack pins its children to min-content, so
        # proportions could never grow a pane past its natural width, and `proportions` has no
        # way to express a fixed-size handle — at proportion 0 rio's max(natural / proportion)
        # min-size pass divides by zero, and the resulting `Infinitypx` is dropped by the CSS
        # parser, silently costing the container its content-derived minimum.
        horizontal = self.direction == 'horizontal'
        size_attr = 'min_width' if horizontal else 'min_height'
        hit_size = max(self.handle_size, self.handle_hit_size)

        # Handles are fixed and sit outside the split, so their width comes off the top before
        # the rest is shared out. Empty until the first on_resize; panes grow evenly until then.
        measured = self._component_width if horizontal else self._component_height
        available = measured - max(len(self.children) - 1, 0) * hit_size - 2 * len(self.children)
        total_proportion = sum(self.child_proportions)
        pane_sizes = (
            [available * p / total_proportion for p in self.child_proportions] if available > 0 and total_proportion > 0 else []
        )

        components: list[rio.Component] = []
        for i, child in enumerate(self.children):
            pane = rio.Rectangle(
                content=rio.ScrollContainer(content=child),
                # Growing on top of an exact share would let a pane with wide content steal its
                # neighbor's space, so grow along the split axis only while sizes are unknown.
                # Across the other axis always, so panes fill height the dialog gains.
                grow_x=(not pane_sizes) if horizontal else True,
                grow_y=True if horizontal else (not pane_sizes),
                margin=1,  # counted in `available` above
                **({size_attr: pane_sizes[i]} if pane_sizes else {}),
            )
            components.append(pane)

            if i < len(self.children) - 1:
                handle = rio.PointerEventListener(
                    content=rio.Stack(
                        # PointerEventListener's hit region is exactly its child's rendered box,
                        # so the grabbable area is this invisible one, not the thin bar over it.
                        rio.Rectangle(
                            **{size_attr: hit_size},
                            fill=rio.Color.TRANSPARENT,
                            cursor='move',
                        ),
                        rio.Rectangle(
                            **{size_attr: self.handle_size},
                            fill=rio.Color.from_hex('#808080'),
                            align_x=0.5 if horizontal else None,
                            align_y=None if horizontal else 0.5,
                        ),
                    ),
                    on_drag_move=lambda event, idx=i: self.on_drag(idx, event),
                )
                components.append(handle)

        container = rio.Row if horizontal else rio.Column
        return container(*components, spacing=0)

    @rio.event.on_resize
    def _on_resize(self, event: rio.event.ComponentResizeEvent) -> None:
        self._component_width = event.width
        self._component_height = event.height
