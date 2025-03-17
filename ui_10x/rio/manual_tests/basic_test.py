import os

if __name__ == '__main__':
    assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')
    from ui_10x.platform import ux

    print( ux.Dialog(children=[ux.Label('Message'),ux.Label('Message2')],title='Title').exec() )

    # from functools import partial
    #
    # from rio import project_config, App, Text, TextStyle, ComponentPage, page

    # app = App(
    #     pages=[
    #         ComponentPage( '', '',
    #             build=lambda: ux.VBoxLayout(
    #                 ux.Label('a'),
    #                 ux.PushButton('b',on_press=partial(print, 'b pressed')),
    #             )(),
    #         )
    #     ]
    # )
    # app.run_in_window()
    #





