from core_10x.code_samples.person import Person
from core_10x.ts_store import TsStore

from ui_10x.traitable_editor import TraitableEditor, TraitableView

if __name__ == '__main__':
    db = TsStore.instance_from_uri('mongodb://localhost/test')
    db.begin_using()

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    view = TraitableView.modify(Person,
        #weight_qu   = UiMod(flags = Ui.HIDDEN),
    )
    e = TraitableEditor.editor(p, view = view)
    rc = e.dialog(save=True).exec()



