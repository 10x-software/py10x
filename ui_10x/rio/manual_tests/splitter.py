import rio
from ui_10x.rio.components.splitter import Splitter

# Example app to demonstrate the Splitter component
class SplitterApp(rio.Component):
    def build(self) -> rio.Component:
        return Splitter(
            rio.Text("Pane 1", style="heading3"),
            rio.Text("Pane 2", style="heading3"),
            rio.Text("Pane 3", style="heading3"),
            spacing=0.5,  # Splitter handle width
            min_width_percent=10.0,  # Minimum width for each pane
        )


# Run the app
if __name__ == "__main__":
    app = rio.App(build=SplitterApp)
    app.run_in_window()