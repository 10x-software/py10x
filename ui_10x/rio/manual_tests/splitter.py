import rio
from ui_10x.rio.components.splitter import Splitter

# Example app to demonstrate the Splitter component
class SplitterApp(rio.Component):
    def build(self) -> rio.Component:
        return rio.FlowContainer(
            rio.Column(
            rio.Row(rio.Button('A'),rio.Button('B')),
            Splitter(
            rio.Text("Pane 1", style="heading3"),
            rio.Text("Pane 2", style="heading3"),
            rio.Text("Pane 3", style="heading3"),
            handle_size=0.3,  # Splitter handle width
            min_size_percent=10.0,  # Minimum width for each pane
            direction='horizontal',
            )
            )
        )


# Run the app
if __name__ == "__main__":
    app = rio.App(build=SplitterApp)
    app._run_in_window(debug_mode=True)