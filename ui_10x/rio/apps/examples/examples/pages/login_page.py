from __future__ import annotations

import rio
from infra_10x.mongodb_store import MongoStore  #TODO: backbone
from ui_10x.rio.component_builder import UserSessionContext


@rio.page(
    name="Login/Logout",
    url_segment="",
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
                running, with_auth = MongoStore.is_running_with_auth(runtime_context.host)
                if not running:
                    self.error_message = 'Authentication is not available'
                    return
                if not self.username and with_auth:
                    self.error_message = 'Username is required'
                    return
                runtime_context.traitable_store  = MongoStore.instance(
                    hostname=runtime_context.host,
                    dbname=runtime_context.dbname,
                    username=self.username,
                    password=self.password
                )
                runtime_context.authenticated=True

            except Exception as e:
                self.error_message = f"Login error - try again\n{e}"
                return

            # The login was successful
            self.error_message = ""

        # Done
        finally:
            self._currently_logging_in = False

    async def logout(self, _: rio.TextInputConfirmEvent | None = None) -> None:
        try:
            runtime_context = self.session[UserSessionContext]
            runtime_context.authenticated=False
            runtime_context.mongo_store=None
        except Exception as e:
            self.error_message = f"Logout error\n {e}"
            return

        # The login was successful
        self.error_message = ""

    def build(self) -> rio.Component:
        rows = [
            rio.TextInput(text=self.bind().username,label="Username",on_confirm=self.login),
            rio.TextInput(text=self.bind().password,label="Password",is_secret=True,on_confirm=self.login),
            rio.Button("Sign In", on_press=self.login, is_loading=self._currently_logging_in),
        ] if not self.session[UserSessionContext].authenticated else [
            rio.Button( "Sign Out", on_press=self.logout ),
        ]

        return rio.Card(
            rio.Column(
                rio.Text("Sign In/Sign Out", style="heading1", justify="center"),
                rio.Banner(text=self.error_message, style="danger",margin_top=1),
                *rows,
                spacing=1,
                margin=2,
            ),
            margin_x=0.5,
            align_y=0.5,
            align_x=0.5,
            min_width=24,
        )
