from __future__ import annotations

import rio


class RioTreeItem(rio.Component):
    """Kwargs allowlist for ``TreeItem`` — not mounted in the tree build.

    ``TreeWidget._build_children`` emits ``rio.SimpleTreeItem`` directly so
    Dialog.exec does not reuse Components across build methods. This class
    exists only so ``TreeItem['text']``, ``['on_press']``, etc. pass
    ``ComponentBuilder.__setitem__`` without "not supported" noise.

    Inline edit (``edit_item`` / ``open_persistent_editor``) is Qt-only today;
    Rio ``SimpleTreeItem`` has no equivalent.
    """

    text: str = ''
    on_double_press: rio.EventHandler[[]] = None
    on_press: rio.EventHandler[[]] = None
    tooltip: str | None = None
    children: list[rio.Component] = []
    is_expanded: bool = False

    def build(self):
        # Never mounted — see module docstring on TreeWidget._build_children.
        return rio.Text(self.text)
