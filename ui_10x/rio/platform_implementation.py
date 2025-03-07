from functools import partial
from ui_10x.platform_interface import Label as LabelInterface
from rio import App, Text, Column, Button


def init() -> App:
    return App()

class Label(LabelInterface):
    def __init__(self, text: str):
        self.text = text

    def set_text(self, text: str):
        self.text = text

    def __call__(self):
        return Text(self.text, selectable=False, align_x=0)

class PushButton(Label):
    def __init__(self, text: str, on_press=None):
        super().__init__(text)
        self.on_press = on_press #or lambda: None

    def __call__(self):
        return Button(self.text, on_press=self.on_press)

class VBoxLayout:
    def __init__(self, *children):
        self.children = children

    def __call__(self):
        return Column(*(c() for c in self.children))