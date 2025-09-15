from __future__ import annotations

import rio
from infra_10x.mongodb_store import MongoStore #TODO: backbone
from ui_10x.rio.platform_implementation import UserSessionContext


def guard(event: rio.GuardEvent) -> str | None:
    return "/ce" if event.session[UserSessionContext].authenticated else None

@rio.page(
    name="Login",
    url_segment="",
    guard=guard,
)
class LoginPage(rio.Component):
    username: str = ""
    password: str = ""

    error_message: str = ""

    _currently_logging_in: bool = False

    async def login(self, _: rio.TextInputConfirmEvent | None = None) -> None:
        try:
            self._currently_logging_in = True
            self.force_refresh()

            try:
                runtime_context = self.session[UserSessionContext]
                runtime_context.traitable_store  = MongoStore.instance(
                    hostname=runtime_context.host,
                    dbname=runtime_context.dbname,
                    username=self.username,
                    password=self.password
                )
                runtime_context.authenticated=True

            except Exception as e:
                self.error_message = f"Login error - try again {e}"
                return

            # The login was successful
            self.error_message = ""
            self.session.navigate_to("/ce")

        # Done
        finally:
            self._currently_logging_in = False


    def build(self) -> rio.Component:
        return rio.Card(
            rio.Column(
                rio.Text("Sign In", style="heading1", justify="center"),
                rio.Banner(text=self.error_message, style="danger",margin_top=1),
                rio.TextInput(text=self.bind().username,label="Username",on_confirm=self.login),
                rio.TextInput(text=self.bind().password,label="Password",is_secret=True,on_confirm=self.login),
                rio.Button("Sign In", on_press=self.login, is_loading=self._currently_logging_in),
                spacing=1,
                margin=2,
            ),
            margin_x=0.5,
            align_y=0.5,
            align_x=0.5,
            min_width=24,
        )
