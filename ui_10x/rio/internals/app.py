from __future__ import annotations

import asyncio
import pathlib
from dataclasses import dataclass
from functools import partial
from threading import Thread
from typing import TYPE_CHECKING

import ordered_set
from webview_proc import WebViewProcess

import rio
from rio import app_server, errors, utils

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import uvicorn


@dataclass
class App10x:
    """
    # App10x - a custom App to use in dialog.
    # rio.App is t.final, so App10x wraps rio.App and implements run_in_window
    # --> run webview out-of-process
    # --> run fastapi server in-process
    # --> uses a subclass fo FastAPIServer to create a custom session class
    #   --> custom session class communicates with out-of-process webview (rather than using webview_shim)
    """

    app: rio.App
    webview: WebViewProcess | None = None

    @staticmethod
    def _update_window_size(width: float | None, height: float | None) -> None:
        import webview  # imported here as called in separate process

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
        host = 'localhost'
        port = utils.ensure_valid_port(host, None)
        url = f'http://{host}:{port}'

        server: uvicorn.Server | None = None

        icon_path = asyncio.run(self.app._fetch_icon_as_png_path())

        self.webview = webview = WebViewProcess(
            url=url,
            title=self.app.name,
            maximized=maximized,
            fullscreen=fullscreen,
            icon_path=icon_path,
            func=partial(self._update_window_size, width, height),
        )

        def _on_server_created(_server: uvicorn.Server) -> None:
            nonlocal server
            server = _server

            fastapi_server = server.config.app
            fastapi_server.__class__ = FastapiServer
            fastapi_server.app10x = self
            if on_server_created:
                on_server_created(server)

        try:

            def start_webview_process() -> None:
                webview.start()  # TODO: integrate monitor into webview via callback

                def monitor_process() -> None:
                    webview.join()
                    if server:
                        server.should_exit = True

                Thread(target=monitor_process, daemon=True).start()

            self.app._run_as_web_server(
                host=host,
                port=port,
                quiet=quiet,
                running_in_window=True,
                internal_on_app_start=start_webview_process,
                internal_on_server_created=_on_server_created,
                debug_mode=debug_mode,
            )

        except Exception as e:
            print(f'Error running app: {e}')
        finally:
            if webview.is_alive():
                webview.close()
                webview.join()


class FastapiServer(app_server.FastapiServer):
    app10x: App10x

    async def create_session(self, *args, **kwargs) -> rio.Session:
        session = await super().create_session(*args, **kwargs)
        session.__class__ = Session
        session.app10x = self.app10x
        return session


class Session(rio.Session):
    app10x: App10x

    async def _close(self, close_remote_session: bool) -> None:
        if not self.running_in_window:
            await super()._close(close_remote_session=close_remote_session)

        await super()._close(close_remote_session=False)
        if close_remote_session:
            self.app10x.webview.close()

    async def _get_webview_window(self):
        raise RuntimeError('Should not be called required in out-of-process webview')

    async def set_title(self, title: str) -> None:
        if not self.running_in_window:
            await super().set_title(title)

        self.app10x.webview.set_title(title)

    async def pick_folder(self) -> pathlib.Path:
        if not self.running_in_window:
            return await super().pick_folder()

        return pathlib.Path(self.app10x.webview.pick_folder())

    async def pick_file(
        self,
        *,
        file_types: Iterable[str] | None = None,
        multiple: bool = False,
    ) -> utils.FileInfo | list[utils.FileInfo]:
        if not self.running_in_window:
            return await super().pick_file(file_types=file_types, multiple=multiple)

        # Normalize the file types
        if file_types is not None:
            # Normalize and deduplicate, but maintain the order
            file_types = list(ordered_set.OrderedSet(utils.normalize_file_extension(file_type) for file_type in file_types))

        selected = self.app10x.webview.pick_file(
            file_types=[f'{extension} (*.{extension})' for extension in file_types],
            multiple=multiple,
        )

        if not selected:
            raise errors.NoFileSelectedError()

        return [utils.FileInfo._from_path(path) for path in selected] if multiple else utils.FileInfo._from_path(selected)

    async def save_file(
        self,
        file_contents: pathlib.Path | str | bytes,
        file_name: str = 'Unnamed File',
        *,
        media_type: str | None = None,
        directory: pathlib.Path | None = None,
    ) -> None:
        if not self.running_in_window:
            return await super().save_file(file_contents, file_name, media_type=media_type, directory=directory)

        self.app10x.webview.save_file(
            file_contents=file_contents,
            directory='' if directory is None else str(directory),
            file_name=file_name,
        )


Session._local_methods_ = rio.Session._local_methods_.copy()
Session._remote_methods_ = rio.Session._remote_methods_.copy()
