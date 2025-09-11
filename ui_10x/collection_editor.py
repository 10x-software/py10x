from typing import Any

from core_10x.traitable import Traitable, T, RT, RC
from core_10x.traitable_id import ID
from core_10x.trait_filter import f

from ui_10x.utils import ux, UxSearchableList, ux_push_button, ux_warning, ux_make_scrollable
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.entity_stocker import EntityStocker, StockerPlug

class Collection(Traitable):
    cls: type[Traitable]    = RT()
    filter: f               = RT(T.HIDDEN)

    entity_ids: list[str]   = RT()

    def cls_set(self, t, cls) -> RC:
        assert issubclass(cls, Traitable), f'{cls} is not a Traitable class'
        return self.raw_set_value(t, cls)

    def entity_ids_get(self) -> list[str]:
        return [ entity_id.value for entity_id in self.cls.load_ids() ]

    def refresh(self):
        self.invalidate_value('entities')

class CollectionEditor(Traitable):
    coll: Collection
    current_class: Any
    coll_title: str
    num_panes: int                      = RT(1)

    main_w: ux.Splitter
    searchable_list: UxSearchableList
    stocker: EntityStocker

    current_editor: Any
    current_entity: Traitable

    def current_class_get(self):
        return self.coll.cls

    def stocker_get(self):
        return EntityStocker(plug = StockerPlug(master = self))

    def main_widget(self) -> ux.Widget:
        sp = ux.Splitter(ux.Horizontal)

        left_w = ux.Widget()
        left_lay = ux.VBoxLayout()
        left_w.set_layout(left_lay)

        left_top_lay = ux.HBoxLayout()
        line_w = ux.LineEdit()
        line_w.set_minimum_width(100)
        button_w = ux_push_button('New', callback = self.on_new_entity, style_icon = 'FileIcon' )
        left_top_lay.add_widget(line_w)
        left_top_lay.add_widget(button_w)

        left_lay.add_layout(left_top_lay)

        self.searchable_list = list_w = UxSearchableList(
            text_widget = line_w,
            title       = f'Instances of {self.coll.cls.__name__}',
            choices     = self.coll.entity_ids,
            select_hook = self.on_entity_id_selection,
            sort        = True,
        )
        slw = ux_make_scrollable(list_w, h = ux.SCROLL.OFF)

        left_lay.add_widget(slw)

        sp.set_style_sheet('QSplitter::handle { background-color: darkgrey; }')
        sp.set_handle_width(1)
        sp.add_widget(left_w)
        sp.add_widget(ux.Widget())
        sp.set_stretch_factor(0, 1)
        sp.set_stretch_factor(1, 2)     #-- TODO: set it for extra panes as needed

        self.main_w = sp
        return sp

    def set_pane(self, index: int, w: ux.Widget):
        main_w = self.main_w
        assert main_w, f'{self.__class__} - no widget has been created yet'

        num_panes = self.num_panes
        if num_panes and 0 <= index < num_panes:
            if index < num_panes:
                main_w.replace_widget(index + 1, w)
            else:
                main_w.add_widget(w)
                self.num_panes = num_panes + 1

    def on_entity_id_selection(self, id_value: str):
        if self.num_panes:
            obj: Traitable = self.coll.cls(_id = ID(id_value))
            se = self.stocker
            ed = se or TraitableEditor.editor(obj)
            self.current_entity = obj
            self.current_editor = ed
            w = ed.main_widget()
            self.set_pane(0, w)

    def on_new_entity(self, flag):
        cls = self.current_class
        if cls:
            new_entity = cls()
            ed = TraitableEditor.editor(new_entity)
            if ed.popup(copy_entity = False, title = f'New Entity of {cls.__name__}', save = True):
                rc = new_entity.save()
                if not rc:
                    ux_warning(rc.error(), parent = self.main_w, on_close = lambda ctx: None)
                    #-- TODO: should we "merge" values from the existing instance?

                else:
                    self.searchable_list.add_choice(new_entity.id().value)
