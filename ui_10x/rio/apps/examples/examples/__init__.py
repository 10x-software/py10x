from __future__ import annotations

import rio

from core_10x.exec_control import INTERACTIVE
from infra_10x.mongodb_store import MongoStore


theme = rio.Theme.from_colors(
    primary_color=rio.Color.from_hex("01dffdff"),
    secondary_color=rio.Color.from_hex("0083ffff"),
    mode="light",
)

interactive = INTERACTIVE() #TODO: FIX - crashes if instance reference not held
def on_app_start(app):
    MongoStore.instance( hostname="localhost", dbname="test", username="", password="").begin_using() #TODO: backbone
    interactive.begin_using()

app = rio.App(
    name='ui_10x.rio.apps.examples',
    description='Rio pages based on components created using ui_10x.platform_interface',
    theme=theme,
    on_app_start=on_app_start
)

