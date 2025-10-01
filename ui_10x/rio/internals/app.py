from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from threading import Thread
from typing import Any

import fastapi
import uvicorn
import webview
from rio.app import guard_against_rio_run
from webview_proc import WebViewProcess

import rio
from rio import utils, maybes


@dataclass
class App10x:
    """
    # App10x - a custom App to use in dialog.
    # rio.App is t.final, so App10x wraps rio.App and implements run_in_window
    # --> run webview out-of-process
    # --> run fastapi server in-process
    # --> uses a subclass fo FastAPIServer to create a custom session class
    #   --> (only one per process!)
    #   --> custom session class communicates with out-of-process webview (rather than using webview_shim)
    """
    app: rio.App

    @staticmethod
    def _update_window_size(width, height) -> None:
        if width is None and height is None:
            return
        window = webview.windows[0]
        print(f'Current window size: {window.width}x{window.height} pixels')
        pixels_per_rem = window.evaluate_js("""
            let measure = document.createElement('div');
            document.body.appendChild(measure);
            measure.style.height = '1rem';
            let pixels_per_rem = measure.getBoundingClientRect().height * window.devicePixelRatio;
            measure.remove();
            pixels_per_rem;
        """)
        width_in_pixels = window.width if width is None else round(width * pixels_per_rem)
        height_in_pixels = window.height if height is None else round(height * pixels_per_rem)
        print(f'Resizing window to {width_in_pixels}x{height_in_pixels} pixels ({width}x{height} rem at {pixels_per_rem} pixels/rem)')
        window.resize(width_in_pixels, height_in_pixels)

    def _run_in_window(
            self,
            *,
            quiet: bool = True,
            maximized: bool = False,
            fullscreen: bool = False,
            width: float | None = None,
            height: float | None = None,
            debug_mode: bool = False,
            on_server_created: Callable[[uvicorn.Server], None] | None = None,
    ) -> None:
        """
        Internal equivalent of `run_in_window` that takes additional arguments (experimental):
        `debug_mode`: Run the app in debug mode (without calling `apply_monkey_patches` though).
        """

        host = "localhost"
        port = utils.ensure_valid_port(host, None)
        url = f"http://{host}:{port}"

        server: uvicorn.Server | None = None

        # Fetch the icon in the main thread
        icon_path = asyncio.run(self.app._fetch_icon_as_png_path())
        webview = WebViewProcess(
            url=url,
            title=self.app.name,
            maximized=maximized,
            fullscreen=fullscreen,
            icon_path=icon_path,
            func=partial(self._update_window_size,width,height),
        )

        def _on_server_created(serv: uvicorn.Server) -> None:
            nonlocal server
            server = serv
            if on_server_created:
                on_server_created(server)

        try:
            def start_webview_process() -> None:
                webview.start() # TODO: integrate monitor into webview via callback

                def monitor_process():
                    webview.join()
                    if server:
                        server.should_exit = True

                Thread(target=monitor_process, daemon=True).start()

            self._run_as_web_server(
                host=host,
                port=port,
                quiet=quiet,
                running_in_window=True,
                internal_on_app_start=start_webview_process,
                internal_on_server_created=_on_server_created,
                debug_mode=debug_mode,
            )
        except Exception as e:
            print(f"Error running app: {e}")
        finally:
            if webview.is_alive():
                webview.close()
                webview.join()

    def _run_as_web_server(
        self,
        *,
        host: str = "localhost",
        port: int = 8000,
        quiet: bool = False,
        running_in_window: bool = False,
        internal_on_app_start: Callable[[], None] | None = None,
        internal_on_server_created: Callable[[uvicorn.Server], None]
        | None = None,
        base_url: rio.URL | str | None = None,
        debug_mode: bool = False,
    ) -> None:
        """
        Internal equivalent of `run_as_web_server` that takes additional
        arguments.
        """

        port = utils.ensure_valid_port(host, port)

        # Suppress stdout messages if requested
        kwargs = {}

        if quiet:
            kwargs["log_config"] = {
                "version": 1,
                "disable_existing_loggers": True,
                "formatters": {},
                "handlers": {},
                "loggers": {},
            }

        # Create the FastAPI server
        fastapi_app = self._as_fastapi(
            debug_mode=debug_mode,
            running_in_window=running_in_window,
            internal_on_app_start=internal_on_app_start,
            base_url=base_url,
        )

        # Suppress stdout messages if requested
        log_level = "error" if quiet else "info"

        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            log_level=log_level,
            timeout_graceful_shutdown=1,  # Without a timeout, sometimes the server just deadlocks
        )
        server = uvicorn.Server(config)

        if internal_on_server_created is not None:
            internal_on_server_created(server)

        server.run()

    def _as_fastapi(
        self,
        *,
        debug_mode: bool,
        running_in_window: bool,
        internal_on_app_start: Callable[[], Any] | None,
        base_url: rio.URL | str | None,
    ) -> fastapi.FastAPI:
        """
        Internal equivalent of `as_fastapi` that takes additional arguments.
        """
        # Make sure all globals are initialized. This should be done as late as
        # possible, because it depends on which modules have been imported into
        # `sys.modules`.
        maybes.initialize()

        # For convenience, this method can accept a string as the base URL.
        # Convert that
        if isinstance(base_url, str):
            base_url = rio.URL(base_url)

        # Build the fastapi instance
        result = fastapi_server.FastapiServer(
            self,
            debug_mode=debug_mode,
            running_in_window=running_in_window,
            internal_on_app_start=internal_on_app_start,
            base_url=base_url,
        )

        # Call all extension event handlers
        self._call_event_handlers_sync(
            self._extension_on_as_fastapi_handlers,
            rio.ExtensionAsFastapiEvent(
                self,
                result,
            ),
        )

        return result