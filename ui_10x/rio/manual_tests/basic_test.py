import os
from functools import partial

from rio import project_config, App, Text, TextStyle, ComponentPage, page


if __name__ == '__main__':
    assert os.environ.setdefault('UI_PLATFORM', 'Rio') == os.getenv('UI_PLATFORM')
    from ui_10x.platform import ux

    print( ux.Dialog(ux.Label('Message'),title='Title').exec() )

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





