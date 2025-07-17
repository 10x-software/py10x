

if __name__ == '__main__':
    #import os;assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')

    from ui_10x.utils import ux, ux_answer,ux_success,ux_warning

    app = ux.init()

    ret = ux_answer('This is a message box. '*50+'Ok?', title='Message Box Title')

    print(ret)


    ret = ux_success('This is a success message box. '*50+'Ok?', title='Success Message Box Title')
    print(ret)

    ret = ux_warning('This is a warning message box. '*50+'Ok?', title='Warning Message Box Title')
    print(ret)

