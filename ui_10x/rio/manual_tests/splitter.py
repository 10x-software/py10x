from rio.debug.monkeypatches import apply_monkeypatches

import rio
from ui_10x.rio.components.splitter import Splitter


# Example app to demonstrate the Splitter component
class SplitterApp(rio.Component):
    def build(self) -> rio.Component:
        splitter = Splitter(
            rio.Text("Pane 1", style="heading3"),
            rio.Text("Pane 2", style="heading3"),
            rio.Rectangle(content=rio.Container(rio.Container(rio.FlowContainer()))),
            handle_size=0.3,  # Splitter handle width
            direction='horizontal',
        )
        return rio.Container(
            rio.Column(
                rio.Column(
                rio.Row(rio.Button('A'),rio.Button('B')),
                    rio.Container(
                        splitter
                    )
                )
            )
        )


# Run the app
if __name__ == "__main__":
    app = rio.App(build=SplitterApp)
    apply_monkeypatches()
    #app._run_in_window(debug_mode=True)
    app._run_as_web_server(debug_mode=True, port=8080, host='')