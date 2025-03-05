from core_10x.code_samples.person import Person
from core_10x.ui_hint import Ui, UiMod

from ui_10x.traitable_editor import TraitableEditor, TraitableView


if __name__ == '__main__':

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    view = TraitableView.modify(Person,
        #weight_qu   = UiMod(flags = Ui.HIDDEN),
    )
    e = TraitableEditor.editor(p, view = view)
    rc = e.popup()



