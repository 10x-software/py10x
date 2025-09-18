from core_10x.code_samples.person import Person
from infra_10x.mongodb_store import MongoStore

from ui_10x.traitable_editor import TraitableEditor, TraitableView

if __name__ == '__main__':
    db = MongoStore.instance(hostname='localhost', dbname='test')
    db.begin_using()

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    view = TraitableView.modify(Person,
        #weight_qu   = UiMod(flags = Ui.HIDDEN),
    )
    e = TraitableEditor.editor(p, view = view)
    rc = e.dialog(save=True).exec()



