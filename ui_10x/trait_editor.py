from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass

from core_10x_i import BTraitableProcessor

from core_10x.concrete_traits import date_trait, dict_trait, flags_trait, list_trait
from core_10x.entity import Entity
from core_10x.exec_control import BTP
from core_10x.rc import RC
from core_10x.trait import T, Trait, Ui
from core_10x.traitable import traitable_trait

import ui_10x.concrete_trait_widgets  # noqa: F401 - registers trait widgets
from ui_10x.choice import MultiChoice
from ui_10x.py_data_browser import PyDataBrowser
from ui_10x.trait_widget import TraitWidget
from ui_10x.utils import UxDialog, UxStyleSheet, ux, ux_pick_date


@dataclass
class EntityWrapper:
    entity: Entity
    traitable_processor: Callable[[], BTP]

    def set_value(self, trait: Trait, value) -> RC:
        with self.traitable_processor() or nullcontext():
            return self.entity.set_value(trait, value)

    def get_value(self, trait: Trait):
        with self.traitable_processor() or nullcontext():
            value = self.entity.get_value(trait)
            return value

    def is_valid(self, trait: Trait) -> bool:
        with self.traitable_processor() or nullcontext():
            return self.entity.is_valid(trait)

    def invalidate_value(self, trait: Trait) -> None:
        with self.traitable_processor() or nullcontext():
            return self.entity.invalidate_value(trait)

    def get_style_sheet(self, trait: Trait):
        with self.traitable_processor() or nullcontext():
            return self.entity.get_style_sheet(trait)

    def get_choices(self, trait: Trait):
        with self.traitable_processor() or nullcontext():
            return self.entity.get_choices(trait)

    def create_ui_node(self, trait: Trait, callback):
        with self.traitable_processor() or nullcontext():
            return self.entity.bui_class().create_ui_node(self.entity, trait, callback)

    def update_ui_node(self, trait: Trait):
        with self.traitable_processor() or nullcontext():
            return self.entity.bui_class().update_ui_node(self.entity, trait)


class TraitEditor:
    def __init__(
        self, entity, trait: Trait, ui_hint: Ui, custom_callback: Callable[None, None] = None, traitable_processor: Callable[[], BTP] = None
    ):
        self.entity = EntityWrapper(entity, traitable_processor)
        self.trait = trait
        self.widget: TraitWidget | None = None
        self.ui_hint = ui_hint
        self.trait_callback = self._establish_callback(custom_callback)

    def is_read_only(self) -> bool:
        return self.ui_hint.flags_on(Ui.READ_ONLY)

    def _establish_callback(self, custom_callback: Callable[None, None]):
        if custom_callback:
            return custom_callback

        if self.is_read_only():
            return None

        return self.builtin_callback()

    def new_label(self) -> ux.Widget:
        if self.ui_hint.param('right_label', False):
            return ux.Label(' ')

        if self.trait_callback:
            label = ux.PushButton()
            label.set_flat(True)
            label.set_style_sheet('text-align: left')
            label.set_text(self.ui_hint.label + '...')
            label.clicked_connect(lambda v: self.trait_callback(self))
            if self.trait.flags_on(T.EXPENSIVE):
                UxStyleSheet.modify(label, {Ui.FG_COLOR: 'purple', Ui.FONT_STYLE: 'italic'})
                label.set_tool_tip('Reaction on clicking this button may take considerable time...')
        else:
            label = ux.Label(self.ui_hint.label)

        return label

    def new_widget(self, update_self=True) -> TraitWidget:
        tw: TraitWidget = TraitWidget.instance(self)
        assert tw, f'{self.entity.entity.__class__}.{self.trait.name} - unknown trait widget class'

        avg_char_width = tw.font_metrics().average_char_width()
        min_width = self.ui_hint.param('min_width', 0)
        if min_width > 0:
            tw.set_minimum_width(min_width * avg_char_width)

        max_width = self.ui_hint.param('max_width', 0)
        if max_width > 0:
            tw.set_maximum_width(max_width * avg_char_width)

        if update_self:
            self.widget = tw

        return tw

    # ---- Built-in Callbacks

    def date_cb(self):
        ux_pick_date(
            title=f'Pick a date for {self.ui_hint.label}',
            show_date=self.entity.get_value(self.trait),
            on_accept=lambda value: self.entity.set_value(self.trait, value),
        )

    def list_cb(self):
        choices = self.entity.get_value(self.trait)
        mc = MultiChoice(choices=choices)
        w = mc.widget()
        if not w:
            return

        UxDialog(
            w,
            title=f'Choose one or more values for {self.ui_hint.label}',
            accept_callback=lambda ctx: self.entity.set_value(self.trait, mc.values_selected),
        ).show()

    def dict_cb(self):
        data = dict(self.entity.get_value(self.trait))
        rc = PyDataBrowser.edit(data, title=f'Edit {self.trait.ui_hint.label}')  # TODO: callback
        if rc:
            self.entity.set_value(self.trait, data)

    def flags_cb(self):
        flags = self.entity.get_value(self.trait)
        bits_class = self.trait.data_type
        tags_selected = bits_class.data_type.names_from_value(flags)
        mc = MultiChoice(*tags_selected, choices=bits_class.choose_from())
        w = mc.widget()
        if not w:
            return

        UxDialog(
            w,
            title=f'Choose one or more flags for {self.ui_hint.label}',
            accept_callback=lambda ctx: self.entity.set_value(self.trait, mc.values_selected),
        ).show()

    def traitable_cb(self):
        # -- EntityEditor - popup
        ...

    def expensive_cb(self):
        value = self.entity.get_value(self.trait)
        self.widget.set_widget_value(value)
        self.widget.style_sheet.restore()

    def builtin_callback(self):
        cb = self.s_builtin_callbacks.get(self.trait.__class__)
        if not cb:
            if self.trait.flags_on(T.EXPENSIVE):
                cb = self.__class__.expensive_cb

        return cb

    # fmt: off
    s_builtin_callbacks = {
        date_trait:         date_cb,
        list_trait:         list_cb,
        dict_trait:         dict_cb,
        flags_trait:        flags_cb,
        traitable_trait:    traitable_cb,
    }
    # fmt: on
