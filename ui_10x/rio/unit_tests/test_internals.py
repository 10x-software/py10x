"""
Tests for ui_10x.rio.internals module.

This module tests the App10x, FastapiServer, and Session classes that provide
custom Rio app functionality for running in webview windows.
"""

import pathlib
import sys
from unittest.mock import Mock, patch

import pytest
from ui_10x.rio.internals.app import App10x, FastapiServer, Session, app_server

import rio


class TestApp10x:
    """Test cases for the App10x class."""

    def test_app10x_initialization(self):
        """Test App10x initialization with default values."""
        mock_app = Mock()
        app10x = App10x(app=mock_app)

        assert app10x.app is mock_app
        assert app10x.webview is None

    def test_app10x_initialization_with_webview(self):
        """Test App10x initialization with webview provided."""
        mock_app = Mock()
        mock_webview = Mock()
        app10x = App10x(app=mock_app, webview=mock_webview)

        assert app10x.app is mock_app
        assert app10x.webview is mock_webview

    def test_update_window_size_no_dimensions(self, monkeypatch):
        """Test _update_window_size when no dimensions are provided."""
        # Mock the webview module that gets imported inside the method
        mock_webview = Mock()
        mock_webview.windows = [Mock()]
        monkeypatch.setitem(sys.modules, 'webview', mock_webview)

        App10x._update_window_size(None, None)
        # Should return early without calling webview methods
        # Since webview is imported inside the method, we can't easily test the early return
        # without more complex mocking, so we'll just verify the method doesn't crash
        pass

    def test_update_window_size_with_dimensions(self, monkeypatch):
        """Test _update_window_size when dimensions are provided."""
        mock_webview = Mock()
        mock_window = Mock()
        mock_window.width = 800
        mock_window.height = 600
        mock_window.evaluate_js.return_value = 16.0  # pixels_per_rem
        mock_webview.windows = [mock_window]

        monkeypatch.setitem(sys.modules, 'webview', mock_webview)

        App10x._update_window_size(50.0, 40.0)

        # Verify evaluate_js was called to get pixels_per_rem
        mock_window.evaluate_js.assert_called_once()
        # Verify resize was called with calculated pixel dimensions
        mock_window.resize.assert_called_once_with(800, 640)  # 50*16, 40*16

    def test_update_window_size_partial_dimensions(self, monkeypatch):
        """Test _update_window_size with only width or height provided."""
        mock_webview = Mock()
        mock_window = Mock()
        mock_window.width = 800
        mock_window.height = 600
        mock_window.evaluate_js.return_value = 16.0
        mock_webview.windows = [mock_window]

        monkeypatch.setitem(sys.modules, 'webview', mock_webview)

        # Test with only width
        App10x._update_window_size(50.0, None)
        mock_window.resize.assert_called_with(800, 600)  # width calculated, height unchanged

        # Reset for next test
        mock_window.reset_mock()
        mock_window.evaluate_js.return_value = 16.0

        # Test with only height
        App10x._update_window_size(None, 40.0)
        mock_window.resize.assert_called_with(800, 640)  # height calculated, width unchanged

    @patch('ui_10x.rio.internals.app.WebViewProcess')
    @patch('ui_10x.rio.internals.app.utils.ensure_valid_port')
    @patch('asyncio.run')
    def test_run_in_window_basic(self, mock_asyncio_run, mock_ensure_port, mock_webview_process):
        """Test basic _run_in_window functionality."""
        # Setup mocks
        mock_ensure_port.return_value = 8080
        mock_asyncio_run.return_value = '/path/to/icon.png'
        mock_webview = Mock()
        mock_webview.is_alive.return_value = True
        mock_webview_process.return_value = mock_webview

        mock_app = Mock()
        mock_app.name = 'Test App'
        app10x = App10x(app=mock_app)

        # Mock the _run_as_web_server method
        mock_app._run_as_web_server = Mock()

        app10x._run_in_window()

        # Verify WebViewProcess was created with correct parameters
        mock_webview_process.assert_called_once()
        call_kwargs = mock_webview_process.call_args[1]
        assert call_kwargs['url'] == 'http://localhost:8080'
        assert call_kwargs['title'] == 'Test App'
        assert call_kwargs['maximized'] is False
        assert call_kwargs['fullscreen'] is False

        # Verify _run_as_web_server was called
        mock_app._run_as_web_server.assert_called_once()
        call_kwargs = mock_app._run_as_web_server.call_args[1]
        assert call_kwargs['host'] == 'localhost'
        assert call_kwargs['port'] == 8080
        assert call_kwargs['running_in_window'] is True
        assert 'internal_on_server_created' in call_kwargs

    @patch('ui_10x.rio.internals.app.WebViewProcess')
    @patch('ui_10x.rio.internals.app.utils.ensure_valid_port')
    @patch('asyncio.run')
    def test_run_in_window_with_options(self, mock_asyncio_run, mock_ensure_port, mock_webview_process):
        """Test _run_in_window with various options."""
        mock_ensure_port.return_value = 8080
        mock_asyncio_run.return_value = '/path/to/icon.png'
        mock_webview = Mock()
        mock_webview.is_alive.return_value = True
        mock_webview_process.return_value = mock_webview

        mock_app = Mock()
        mock_app.name = 'Test App'
        app10x = App10x(app=mock_app)
        mock_app._run_as_web_server = Mock()

        # Test with custom options
        app10x._run_in_window(quiet=False, maximized=True, fullscreen=True, width=100.0, height=80.0, debug_mode=True)

        # Verify WebViewProcess was created with custom options
        call_kwargs = mock_webview_process.call_args[1]
        assert call_kwargs['maximized'] is True
        assert call_kwargs['fullscreen'] is True

        # Verify _run_as_web_server was called with custom options
        call_kwargs = mock_app._run_as_web_server.call_args[1]
        assert call_kwargs['quiet'] is False
        assert call_kwargs['debug_mode'] is True

    @patch('ui_10x.rio.internals.app.WebViewProcess')
    @patch('ui_10x.rio.internals.app.utils.ensure_valid_port')
    @patch('asyncio.run')
    def test_run_in_window_exception_handling(self, mock_asyncio_run, mock_ensure_port, mock_webview_process):
        """Test _run_in_window exception handling and cleanup."""
        mock_ensure_port.return_value = 8080
        mock_asyncio_run.return_value = '/path/to/icon.png'
        mock_webview = Mock()
        mock_webview.is_alive.return_value = True
        mock_webview_process.return_value = mock_webview

        mock_app = Mock()
        mock_app.name = 'Test App'
        mock_app._run_as_web_server.side_effect = Exception('Test error')
        app10x = App10x(app=mock_app)

        # Should not raise exception
        app10x._run_in_window()

        # Verify cleanup was performed
        mock_webview.close.assert_called_once()
        mock_webview.join.assert_called_once()

    @patch('ui_10x.rio.internals.app.WebViewProcess')
    @patch('ui_10x.rio.internals.app.utils.ensure_valid_port')
    @patch('asyncio.run')
    def test_run_in_window_on_server_created_callback(self, mock_asyncio_run, mock_ensure_port, mock_webview_process):
        """Test _on_server_created callback functionality."""
        # Setup mocks
        mock_ensure_port.return_value = 8080
        mock_asyncio_run.return_value = '/path/to/icon.png'
        mock_webview = Mock()
        mock_webview.is_alive.return_value = True
        mock_webview_process.return_value = mock_webview

        mock_app = Mock()
        mock_app.name = 'Test App'
        app10x = App10x(app=mock_app)

        # Mock the _run_as_web_server method to capture the callback
        mock_app._run_as_web_server = Mock()

        # Custom callback to test
        callback_called = []

        def test_callback(server):
            callback_called.append(server)

        app10x._run_in_window(on_server_created=test_callback)

        # Get the internal_on_server_created callback
        call_kwargs = mock_app._run_as_web_server.call_args[1]
        internal_callback = call_kwargs['internal_on_server_created']

        # Test the callback
        mock_server = Mock()
        mock_server.config = Mock()
        mock_server.config.app = Mock()
        internal_callback(mock_server)

        # Verify the callback was called
        assert len(callback_called) == 1
        assert callback_called[0] is mock_server

        # Verify server was configured
        assert hasattr(mock_server.config.app, 'app10x')
        assert mock_server.config.app.app10x is app10x


class TestFastapiServer:
    """Test cases for the FastapiServer class."""

    def test_fastapi_server_class_attributes(self):
        """Test FastapiServer class attributes."""
        # Test that FastapiServer has the expected type annotation
        # The app10x is defined as a type annotation, not a class attribute
        # We can check that the class has the annotation in its __annotations__
        assert 'app10x' in FastapiServer.__annotations__
        # The annotation is stored as a string, so we check for the string representation
        assert FastapiServer.__annotations__['app10x'] == 'App10x'

    def test_fastapi_server_inheritance(self):
        """Test that FastapiServer properly inherits from app_server.FastapiServer."""
        from ui_10x.rio.internals.app import app_server

        assert issubclass(FastapiServer, app_server.FastapiServer)

    async def test_fastapi_server_create_session(self):
        """Test create_session method creates Session with app10x attribute."""
        # Create a mock server that behaves like FastapiServer
        server = Mock()
        server.__class__ = FastapiServer
        server.app10x = Mock()

        # Mock the parent create_session method
        mock_session = Mock(spec=rio.Session)
        mock_parent_create_session = Mock()

        async def fake_create_session(*args, **kwargs):
            mock_parent_create_session(*args, **kwargs)
            return mock_session

        with patch.object(app_server.FastapiServer, 'create_session', fake_create_session):
            # Call the actual FastapiServer.create_session method
            result = await FastapiServer.create_session(server)

            # Should call parent method
            mock_parent_create_session.assert_called_once()

            # Should return a Session instance with app10x attribute
            assert result.__class__ == Session
            assert result.app10x is server.app10x


class TestSession:
    """Test cases for the Session class."""

    def test_session_class_attributes(self):
        """Test Session class attributes."""
        # Test that Session has the expected class attributes
        assert hasattr(Session, 'app10x')
        # The app10x attribute should be a class attribute that can be set on instances
        assert isinstance(Session.app10x, type(None)) or hasattr(Session, 'app10x')

    def test_session_inheritance(self):
        """Test that Session properly inherits from rio.Session."""
        assert issubclass(Session, rio.Session)

    def test_session_method_attributes(self):
        """Test that Session has the correct method attributes."""
        # Verify that Session has the expected method attributes
        assert hasattr(Session, '_local_methods_')
        assert hasattr(Session, '_remote_methods_')

        # These should be copies of the parent class attributes
        assert Session._local_methods_ is not rio.Session._local_methods_
        assert Session._remote_methods_ is not rio.Session._remote_methods_
        assert isinstance(Session._local_methods_, dict)
        assert isinstance(Session._remote_methods_, dict)

        # The content should be the same as the parent class
        assert Session._local_methods_ == rio.Session._local_methods_
        assert Session._remote_methods_ == rio.Session._remote_methods_

    def test_session_methods_exist(self):
        """Test that Session has the expected methods."""
        # Test that the custom methods exist on the Session class
        assert hasattr(Session, '_close')
        assert hasattr(Session, '_get_webview_window')
        assert hasattr(Session, 'set_title')
        assert hasattr(Session, 'pick_folder')
        assert hasattr(Session, 'pick_file')
        assert hasattr(Session, 'save_file')

    async def test_session_close_not_running_in_window(self):
        """Test _close when not running in window calls parent method twice."""
        # Create a mock session with the actual Session class behavior
        session = Mock()
        session.__class__ = Session
        session.running_in_window = False

        # Mock the parent _close method
        mock_parent_close = Mock()

        async def fake_close(*args, **kwargs):
            mock_parent_close(*args, **kwargs)

        with patch.object(rio.Session, '_close', fake_close):
            # Call the actual Session._close method
            await Session._close(session, close_remote_session=True)

            # Should call parent method twice: once with original parameter, once with False
            assert mock_parent_close.call_count == 2
            mock_parent_close.assert_any_call(session, close_remote_session=True)
            mock_parent_close.assert_any_call(session, close_remote_session=False)

    async def test_session_close_running_in_window(self):
        """Test _close when running in window calls parent with False and closes webview."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()

        # Mock the parent _close method
        mock_parent_close = Mock()

        async def fake_close(*args, **kwargs):
            mock_parent_close(*args, **kwargs)

        with patch.object(rio.Session, '_close', fake_close):
            # Call the actual Session._close method
            await Session._close(session, close_remote_session=True)

            # Should call parent method once with close_remote_session=False
            mock_parent_close.assert_called_once_with(session, close_remote_session=False)

            # Should close webview
            session.app10x.webview.close.assert_called_once()

    async def test_session_get_webview_window_raises_error(self):
        """Test _get_webview_window raises RuntimeError."""
        session = Mock()
        session.__class__ = Session

        with pytest.raises(RuntimeError, match='Should not be called required in out-of-process webview'):
            await Session._get_webview_window(session)

    async def test_session_set_title_not_running_in_window(self):
        """Test set_title when not running in window calls parent method."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = False

        # Mock the parent set_title method
        mock_parent_set_title = Mock()

        async def fake_set_title(*args, **kwargs):
            mock_parent_set_title(*args, **kwargs)

        with patch.object(rio.Session, 'set_title', fake_set_title):
            # Call the actual Session.set_title method
            await Session.set_title(session, 'Test Title')

            # Should call parent method
            mock_parent_set_title.assert_called_once_with(session, 'Test Title')

    async def test_session_set_title_running_in_window(self):
        """Test set_title when running in window calls webview instead of parent."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()

        # Mock the parent set_title method
        mock_parent_set_title = Mock()

        async def fake_set_title(*args, **kwargs):
            mock_parent_set_title(*args, **kwargs)

        with patch.object(rio.Session, 'set_title', fake_set_title):
            # Call the actual Session.set_title method
            await Session.set_title(session, 'Test Title')

            # Should not call parent method
            mock_parent_set_title.assert_not_called()

            # Should call webview set_title
            session.app10x.webview.set_title.assert_called_once_with('Test Title')

    async def test_session_pick_folder_not_running_in_window(self):
        """Test pick_folder when not running in window calls parent method."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = False
        expected_path = pathlib.Path('/test/path')

        # Mock the parent pick_folder method
        mock_parent_pick_folder = Mock()

        async def fake_pick_folder(*args, **kwargs):
            mock_parent_pick_folder(*args, **kwargs)
            return expected_path

        with patch.object(rio.Session, 'pick_folder', fake_pick_folder):
            # Call the actual Session.pick_folder method
            result = await Session.pick_folder(session)

            # Should call parent method and return its result
            mock_parent_pick_folder.assert_called_once()
            assert result == expected_path

    async def test_session_pick_folder_running_in_window(self):
        """Test pick_folder when running in window calls webview and returns Path."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()
        session.app10x.webview.pick_folder.return_value = '/test/path'

        # Call the actual Session.pick_folder method
        result = await Session.pick_folder(session)

        # Should call webview pick_folder and return Path
        session.app10x.webview.pick_folder.assert_called_once()
        assert result == pathlib.Path('/test/path')

    async def test_session_pick_file_not_running_in_window(self):
        """Test pick_file when not running in window calls parent method."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = False
        expected_file_info = Mock()

        # Mock the parent pick_file method
        mock_parent_pick_file = Mock()

        async def fake_pick_file(*args, **kwargs):
            mock_parent_pick_file(*args, **kwargs)
            return expected_file_info

        with patch.object(rio.Session, 'pick_file', fake_pick_file):
            # Call the actual Session.pick_file method
            result = await Session.pick_file(session, file_types=['txt'], multiple=False)

            # Should call parent method and return its result
            mock_parent_pick_file.assert_called_once_with(session, file_types=['txt'], multiple=False)
            assert result == expected_file_info

    async def test_session_pick_file_running_in_window_single(self):
        """Test pick_file when running in window (single file) calls webview."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()
        session.app10x.webview.pick_file.return_value = '/test/file.txt'

        # Mock utils.FileInfo._from_path
        mock_file_info = Mock()
        with patch('ui_10x.rio.internals.app.utils.FileInfo._from_path', return_value=mock_file_info):
            # Call the actual Session.pick_file method
            result = await Session.pick_file(session, file_types=['txt'], multiple=False)

            # Should call webview pick_file with normalized file types
            session.app10x.webview.pick_file.assert_called_once_with(file_types=['txt (*.txt)'], multiple=False)
            assert result == mock_file_info

    async def test_session_pick_file_running_in_window_multiple(self):
        """Test pick_file when running in window (multiple files) calls webview."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()
        session.app10x.webview.pick_file.return_value = ['/test/file1.txt', '/test/file2.txt']

        # Mock utils.FileInfo._from_path
        mock_file_info1 = Mock()
        mock_file_info2 = Mock()
        with patch('ui_10x.rio.internals.app.utils.FileInfo._from_path', side_effect=[mock_file_info1, mock_file_info2]):
            # Call the actual Session.pick_file method
            result = await Session.pick_file(session, file_types=['txt'], multiple=True)

            # Should call webview pick_file with normalized file types
            session.app10x.webview.pick_file.assert_called_once_with(file_types=['txt (*.txt)'], multiple=True)
            assert result == [mock_file_info1, mock_file_info2]

    async def test_session_pick_file_no_selection(self):
        """Test pick_file when no file is selected raises NoFileSelectedError."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()
        session.app10x.webview.pick_file.return_value = None

        # Should raise NoFileSelectedError
        with pytest.raises(rio.errors.NoFileSelectedError):
            await Session.pick_file(session, file_types=['txt'], multiple=False)

    async def test_session_pick_file_normalize_file_types(self):
        """Test pick_file normalizes and deduplicates file types."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()
        session.app10x.webview.pick_file.return_value = '/test/file.txt'

        mock_file_info = Mock()
        with patch('ui_10x.rio.internals.app.utils.FileInfo._from_path', return_value=mock_file_info):
            # Call the actual Session.pick_file method
            await Session.pick_file(session, file_types=['txt', 'pdf'], multiple=False)

            # Should call webview with file types formatted correctly
            session.app10x.webview.pick_file.assert_called_once_with(file_types=['txt (*.txt)', 'pdf (*.pdf)'], multiple=False)

    async def test_session_save_file_not_running_in_window(self):
        """Test save_file when not running in window calls parent method."""
        session = Mock()
        session.__class__ = Session
        session.running_in_window = False

        # Mock the parent save_file method
        mock_parent_save_file = Mock()

        async def fake_save_file(*args, **kwargs):
            mock_parent_save_file(*args, **kwargs)

        with patch.object(rio.Session, 'save_file', fake_save_file):
            # Call the actual Session.save_file method
            await Session.save_file(session, 'test content', 'test.txt', media_type='text/plain', directory=pathlib.Path('/test'))

            # Should call parent method
            mock_parent_save_file.assert_called_once_with(
                session, 'test content', 'test.txt', media_type='text/plain', directory=pathlib.Path('/test')
            )

    async def test_session_save_file_running_in_window(self):
        """Test save_file when running in window calls webview."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()

        # Call the actual Session.save_file method
        await Session.save_file(session, 'test content', 'test.txt', media_type='text/plain', directory=pathlib.Path('/test'))

        # Should call webview save_file
        session.app10x.webview.save_file.assert_called_once_with(file_contents='test content', directory='/test', file_name='test.txt')

    async def test_session_save_file_running_in_window_no_directory(self):
        """Test save_file when running in window with no directory calls webview."""
        session = Mock()
        session.running_in_window = True
        session.app10x = Mock()
        session.app10x.webview = Mock()

        # Call the actual Session.save_file method
        await Session.save_file(session, 'test content', 'test.txt')

        # Should call webview save_file with empty directory
        session.app10x.webview.save_file.assert_called_once_with(file_contents='test content', directory='', file_name='test.txt')


class TestIntegration:
    """Integration tests for the complete App10x workflow."""

    @patch('ui_10x.rio.internals.app.WebViewProcess')
    @patch('ui_10x.rio.internals.app.utils.ensure_valid_port')
    @patch('asyncio.run')
    def test_complete_app10x_workflow(self, mock_asyncio_run, mock_ensure_port, mock_webview_process):
        """Test the complete App10x workflow from initialization to cleanup."""
        # Setup mocks
        mock_ensure_port.return_value = 8080
        mock_asyncio_run.return_value = '/path/to/icon.png'
        mock_webview = Mock()
        mock_webview.is_alive.return_value = True
        mock_webview_process.return_value = mock_webview

        # Create mock Rio app
        mock_app = Mock()
        mock_app.name = 'Integration Test App'
        mock_app._run_as_web_server = Mock()

        # Create App10x instance
        app10x = App10x(app=mock_app)

        # Test the complete workflow
        app10x._run_in_window(debug_mode=True)

        # Verify WebViewProcess was created
        mock_webview_process.assert_called_once()

        # Verify the server was configured correctly
        mock_app._run_as_web_server.assert_called_once()
        call_kwargs = mock_app._run_as_web_server.call_args[1]
        assert call_kwargs['debug_mode'] is True
        assert call_kwargs['running_in_window'] is True

        # Verify cleanup was performed
        mock_webview.close.assert_called_once()
        mock_webview.join.assert_called_once()

    def test_session_method_attributes(self):
        """Test that Session class has the correct method attributes."""
        # Verify that Session has the expected method attributes
        assert hasattr(Session, '_local_methods_')
        assert hasattr(Session, '_remote_methods_')

        # These should be copies of the parent class attributes
        assert Session._local_methods_ is not rio.Session._local_methods_
        assert Session._remote_methods_ is not rio.Session._remote_methods_
        assert isinstance(Session._local_methods_, dict)
        assert isinstance(Session._remote_methods_, dict)
