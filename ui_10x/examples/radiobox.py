if __name__ == '__main__':
    #import os;assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')
    from core_10x.rc import RC_TRUE

    from ui_10x.utils import UxDialog, UxRadioBox, ux
    from ui_10x.examples.constants import COLOR


    ux.init()
    w = UxRadioBox(COLOR, 'Choose a Color', default_value = COLOR.GREEN)
    def cb():
        print('accept:', w.choice() )
        return RC_TRUE

    d = UxDialog(w, accept_callback = cb)
    rc = d.exec()
    print(w.choice(), rc)


