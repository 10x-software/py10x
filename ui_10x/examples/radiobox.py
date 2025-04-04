

if __name__ == '__main__':
    #import os;assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')

    from ui_10x.utils import ux, UxRadioBox, UxDialog

    from core_10x.named_constant import NamedConstant

    class COLOR(NamedConstant, lowercase_values = True):
        BLACK   = ()
        WHITE   = ()
        GREEN   = ()
        RED     = ()
        BROWN   = ()

    app = ux.init()

    w = UxRadioBox(COLOR, 'Choose a Color', default_value = COLOR.GREEN)
    d = UxDialog(w)

    rc = d.exec()

    print(w.choice(),rc)


