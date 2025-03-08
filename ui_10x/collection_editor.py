from core_10x.traitable import Traitable, T, RT, RC, Ui
from core_10x.ts_store import TsStore, TsCollection
from core_10x.trait_filter import f

from ui_10x.utils import ux, UxSearchableList
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.entity_stocker import EntityStocker, StockerPlug

class Collection(Traitable):
    cls: type           = RT()
    filter: f           = RT(T.HIDDEN)

    entities: list      = RT()

    def cls_set(self, t, cls) -> RC:
        assert issubclass(cls, Traitable), f'{cls} is not a Traitable class'
        return self.raw_set_value(t, cls)

    def entities_get(self) -> list:
        #return self.cls.load_many(self.f)
        return self.cls.load_ids()

    def refresh(self):
        self.invalidate_value('entities')

class CollectionEditor(Traitable):
    coll: Collection                    = RT()
    current_class                       = RT()
    coll_title: str                     = RT()
    num_panes: int                      = RT(1)

    main_w: ux.Widget                   = RT()
    searchable_list: ux.Widget          = RT()
    stocker: EntityStocker              = RT()

    current_editor                      = RT()
    current_entity: Traitable           = RT()

    def current_class_get(self):
        return self.coll.cls

    def stocker_get(self):
        return EntityStocker(plug = StockerPlug(master = self))

    def searchable_list_get(self) -> list:
        return UxSearchableList(
            title   = f'Instances of {self.coll.cls.__name__}',
            choices = self.coll.entities,
            select_hook = self.on_entity_id_selection,
            sort    = True,
        )

    def main_widget(self) -> ux.Widget:
        sp = ux.Splitter(ux.Horizontal)
        sp.set_style_sheet('QSplitter::handle { background-color: darkgrey; }')
        sp.set_handle_width(1)
        sp.add_widget(self.searchable_list)
        sp.add_widget(ux.Widget())
        sp.set_stretch_factor(0, 0)
        sp.set_stretch_factor(1, 1)     #-- TODO: set it for extra panes as needed

        self.main_w = sp
        return sp

    def set_pane(self, index: int, w: ux.Widget):
        main_w = self.main_w
        assert main_w, f'{self.__class__} - no widget has been created yet'

        num_panes = self.num_panes
        if num_panes and index >= 0 and index < num_panes:
            if index < num_panes:
                main_w.replace_widget(index + 1, w)
            else:
                main_w.add_widget(w)
                self.num_panes = num_panes + 1

    def on_entity_id_selection(self, id_value: str):
        if self.num_panes:
            obj: Traitable = self.coll.cls(_id = id_value)
            se = self.stocker
            ed = se or TraitableEditor.editor(obj)
            self.current_entity = obj
            self.current_editor = ed
            w = ed.main_widget()
            self.set_pane(0, w)
