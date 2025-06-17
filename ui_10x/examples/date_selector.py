from core_10x.rc import RC

if __name__ == '__main__':
    #import os;assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')

    from ui_10x.utils import ux, UxDialog, ux_pick_date


    app = ux.init()

    ux_pick_date(on_accept=lambda value: print(value) or RC(True))

    print(ux_pick_date())

