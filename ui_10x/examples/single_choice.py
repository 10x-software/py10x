if __name__ == '__main__':
    from core_10x.code_samples.directories import ANIMALS, FISH

    from ui_10x.utils import ux, UxDialog
    from ui_10x.choice import Choice

    ux.init()

    choice1 = Choice(choices = ANIMALS)
    d = UxDialog(choice1.widget())
    d.exec()

    print(choice1.values_selected)

    choice2 = Choice(choices = FISH)
    d = UxDialog(choice2.widget())
    d.exec()

    print(choice2.values_selected)

    choice3 = Choice(choices = FISH.choices())

    d = UxDialog(choice3.widget())
    d.exec()

    print(choice3.values_selected)

    choice3.popup()
    print(choice3.values_selected)
