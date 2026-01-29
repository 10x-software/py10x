from core_10x.exec_control import INTERACTIVE
from core_10x.py_class import PyClass
from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE, AnonymousTraitable
from core_10x.directory import Directory

from ui_10x.py_data_browser import PyDataBrowser
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.traitable_view import TraitableView, Ui, UiMod
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.utils import ux, UxDialog

class CEApp(Traitable):
    s_exclude_packages = ('manual_tests', 'unit_tests')

    top_package: str        = RT()#Ui(label = 'Package'))
    exclude_packages: list  = RT(Ui(flags = Ui.HIDDEN))
    current_class: type     = RT(Ui.choice(stretch = 1))

    my_editor: TraitableEditor  = RT(Ui(flags = Ui.HIDDEN))
    col_editor: CollectionEditor = RT(Ui(flags = Ui.HIDDEN))
    main_w: ux.Splitter         = RT(Ui(flags = Ui.HIDDEN))

    def exclude_packages_get(self) -> list:
        root_name = self.top_package
        return [f'{root_name}.{name}' for name in self.s_exclude_packages]

    def current_class_set(self, trait, value) -> RC:
        self.raw_set_value(trait, value)
        coll = Collection(cls = value)
        ce = CollectionEditor(coll = coll)
        self.col_editor = ce
        w = ce.main_widget()
        self.main_w.replace_widget(0, w)

        return RC_TRUE

    def current_class_choices(self, trait) -> Directory:
        all_traitables = PyClass.all_classes(self.top_package, exclude_packages = self.exclude_packages, parent_classes = (Traitable,))
        all_storables = tuple(cls for cls in all_traitables if cls.is_storable() and not issubclass(cls, AnonymousTraitable))
        dir = Directory(name = 'Classes')
        for cls in all_storables:
            path = cls.__module__.split('.')
            dir.insert(PyClass.name(cls), *path)

        return dir

    def my_editor_get(self) -> TraitableEditor:
        return TraitableEditor.editor(self)

    def main_widget(self) -> ux.Widget:
        w = ux.Widget()
        lay = ux.VBoxLayout()
        w.set_layout(lay)

        lay.add_layout(self.my_editor.row_layout())
        lay.add_widget(ux.separator())

        sp = ux.Splitter(ux.Horizontal)
        lay.add_widget(sp)

        sp.set_style_sheet('QSplitter::handle { background-color: darkgrey; }')
        sp.set_handle_width(1)

        sp.add_widget(ux.Widget())
        sp.set_stretch_factor(0, 1)
        sp.set_stretch_factor(1, 2)  #-- TODO: set it for extra panes as needed

        self.main_w = sp

        return w

if __name__ == '__main__':
    from ui_10x.apps.collection_editor_app import CEApp

    ux.init()

    ce_app = CEApp(top_package = 'core_10x')

    with INTERACTIVE():
        # coll = Collection(cls = Person)
        # ce = CollectionEditor(coll = coll)
        # w = ce.main_widget()
        # d = UxDialog(w)
        # d.exec()
        w = ce_app.main_widget()
        d = UxDialog(w)
        d.exec()
