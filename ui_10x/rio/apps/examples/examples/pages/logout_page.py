from __future__ import annotations

import rio
from ui_10x.rio.platform_implementation import UserSessionContext


def guard(event: rio.GuardEvent) -> str | None:
    return None if event.session[UserSessionContext].authenticated else '/'

@rio.page(
    name="Logout",
    url_segment="logout",
    guard=guard,
)
class LogoutPage(rio.Component):
    error_message: str = ''

    async def logout(self, _: rio.TextInputConfirmEvent | None = None) -> None:
        try:
            runtime_context = self.session[UserSessionContext]
            runtime_context.authenticated=False
            runtime_context.mongo_store=None
        except Exception as e:
            self.error_message = f"Logout error\n {e}"
            return
        self.session.navigate_to("/")


    def build(self) -> rio.Component:
        return rio.Card(
            rio.Column(
                rio.Text("Sign Out", style="heading1", justify="center"),
                rio.Banner(
                    text=self.error_message,
                    style="danger",
                    margin_top=1,
                ),
                rio.Button( "Sign Out", on_press=self.logout ),
                spacing=1,
                margin=2
            ),
            margin_x=0.5,
            align_y=0.5,
            align_x=0.5
        )

