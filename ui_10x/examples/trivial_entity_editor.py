from core_10x.code_samples.person import Person
from core_10x.ui_hint import Ui, UiHintModification

from ui_10x.traitable_editor import TraitableEditor, TraitableView


if __name__ == '__main__':

    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    view = TraitableView.modify(
        Person,
        weight_qu   = UiHintModification(flags = Ui.HIDDEN),
        older_than  = UiHintModification(flags = Ui.HIDDEN)
    )
    e = TraitableEditor(p, view = view)

    e.popup(copy_entity = False)

