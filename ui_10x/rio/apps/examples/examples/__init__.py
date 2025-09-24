from __future__ import annotations

from core_10x.exec_control import INTERACTIVE
from ui_10x.rio.component_builder import UserSessionContext

import rio

theme = rio.Theme.from_colors(
    primary_color=rio.Color.from_hex('01dffdff'),
    secondary_color=rio.Color.from_hex('0083ffff'),
)


def on_session_start(session):
    session.attach(UserSessionContext(host='localhost', dbname='test')) # TODO: backbone

app = rio.App(
    name='ui_10x.rio.apps.examples',
    description='Rio pages based on components created using ui_10x.platform_interface',
    theme=theme,
    on_session_start=on_session_start,
)
