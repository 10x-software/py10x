# App10x - a custom App to use in dialog.
# rio.App is t.final, so App10x wraps rio.App and implements run_in_window
# --> run webview out-of-process
# --> run fastapi server in-process
# --> uses a subclass fo FastAPIServer to create a custom session class
#   --> (only one per process!)
#   --> custom session class communicates with out-of-process webview (rather than using webview_shim)


