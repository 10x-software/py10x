from __future__ import annotations

import rio

from core_10x.exec_control import INTERACTIVE
from ui_10x.rio.platform_implementation import UserSessionContext

theme = rio.Theme.from_colors(
    primary_color=rio.Color.from_hex("01dffdff"),
    secondary_color=rio.Color.from_hex("0083ffff"),
    mode="light",
)

def on_session_start(session):
    session.attach(UserSessionContext(host="localhost", dbname="test")) #TODO: backbone

interactive = None #TODO: crashes without global reference
def on_app_start(app):
    global interactive
    interactive = INTERACTIVE()
    interactive.begin_using() # TODO: ideally should be in UserSessionContext, but needs to be re-enterable then

app = rio.App(
    name='ui_10x.rio.apps.examples',
    description='Rio pages based on components created using ui_10x.platform_interface',
    theme=theme,
    on_app_start=on_app_start,
    on_session_start=on_session_start,
)