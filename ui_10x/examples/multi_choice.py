if __name__ == '__main__':
    from core_10x.code_samples.directories import ANIMALS

    from ui_10x.choice import MultiChoice
    from ui_10x.utils import UxDialog, ux

    ux.init()

    choice1 = MultiChoice(choices = ANIMALS)

    d = UxDialog(choice1.widget())
    d.exec()

    choice2 = MultiChoice(choices = ANIMALS.choices())

    d = UxDialog(choice2.widget())
    d.exec()
