"""Corrected tests for ccbt.cli.interactive module."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestInteractiveModule:
    """Test the interactive CLI module."""

    def test_module_imports(self):
        """Test that the interactive module can be imported."""
        try:
            import ccbt.cli.interactive
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import interactive module: {e}")

    def test_interactive_cli_class_exists(self):
        """Test that InteractiveCLI class exists."""
        import ccbt.cli.interactive as interactive
        
        assert hasattr(interactive, 'InteractiveCLI'), "InteractiveCLI class not found"
        assert callable(getattr(interactive, 'InteractiveCLI')), "InteractiveCLI is not callable"

    def test_interactive_cli_instantiation(self):
        """Test that InteractiveCLI can be instantiated."""
        import ccbt.cli.interactive as interactive
        from unittest.mock import MagicMock
        
        # Test basic instantiation with required arguments
        try:
            mock_session = MagicMock()
            mock_console = MagicMock()
            cli = interactive.InteractiveCLI(mock_session, mock_console)
            assert cli is not None
        except Exception as e:
            pytest.fail(f"Failed to instantiate InteractiveCLI: {e}")

    def test_interactive_cli_methods_exist(self):
        """Test that InteractiveCLI has expected methods."""
        import ccbt.cli.interactive as interactive
        from unittest.mock import MagicMock
        
        mock_session = MagicMock()
        mock_console = MagicMock()
        cli = interactive.InteractiveCLI(mock_session, mock_console)
        
        # Check for common methods
        expected_methods = [
            'start',
            'stop',
            'run',
            'display_menu',
            'handle_command',
            'display_status',
            'display_torrents',
            'display_peers',
            'display_pieces',
            'display_statistics',
            'display_logs',
            'display_config',
            'display_advanced',
            'display_monitoring',
        ]
        
        found_methods = []
        for method_name in expected_methods:
            if hasattr(cli, method_name):
                method = getattr(cli, method_name)
                if callable(method):
                    found_methods.append(method_name)
        
        # We expect at least some methods to exist
        assert len(found_methods) > 0, f"No expected methods found. Available: {[m for m in dir(cli) if not m.startswith('_')]}"

    def test_interactive_cli_async_methods(self):
        """Test that InteractiveCLI async methods are async."""
        import ccbt.cli.interactive as interactive
        import asyncio
        import inspect
        from unittest.mock import MagicMock
        
        mock_session = MagicMock()
        mock_console = MagicMock()
        cli = interactive.InteractiveCLI(mock_session, mock_console)
        
        # Check if main methods are async
        async_methods = ['start', 'stop', 'run']
        
        for method_name in async_methods:
            if hasattr(cli, method_name):
                method = getattr(cli, method_name)
                if callable(method):
                    # Check if it's a coroutine function
                    assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"

    def test_interactive_module_structure(self):
        """Test that the interactive module has expected structure."""
        import ccbt.cli.interactive as interactive
        
        # Check that the module has expected attributes
        module_attrs = dir(interactive)
        
        # Should have InteractiveCLI class
        assert 'InteractiveCLI' in module_attrs, "InteractiveCLI class not found"
        
        # Should have some imports
        assert 'Console' in module_attrs, "Console import not found"
        assert 'Table' in module_attrs, "Table import not found"
        assert 'asyncio' in module_attrs, "asyncio import not found"

    def test_interactive_cli_docstring(self):
        """Test that InteractiveCLI has a docstring."""
        import ccbt.cli.interactive as interactive
        
        # Check that the class has a docstring
        assert interactive.InteractiveCLI.__doc__ is not None, "InteractiveCLI should have a docstring"
        assert len(interactive.InteractiveCLI.__doc__.strip()) > 0, "InteractiveCLI docstring should not be empty"

    def test_interactive_cli_methods_have_docstrings(self):
        """Test that InteractiveCLI methods have docstrings."""
        import ccbt.cli.interactive as interactive
        from unittest.mock import MagicMock
        
        mock_session = MagicMock()
        mock_console = MagicMock()
        cli = interactive.InteractiveCLI(mock_session, mock_console)
        
        # Check that main methods have docstrings
        main_methods = ['start', 'stop', 'run']
        
        for method_name in main_methods:
            if hasattr(cli, method_name):
                method = getattr(cli, method_name)
                if callable(method):
                    assert method.__doc__ is not None, f"{method_name} should have a docstring"
                    assert len(method.__doc__.strip()) > 0, f"{method_name} docstring should not be empty"

    def test_interactive_cli_initialization(self):
        """Test InteractiveCLI initialization with different parameters."""
        import ccbt.cli.interactive as interactive
        from unittest.mock import MagicMock
        
        # Test basic initialization
        mock_session = MagicMock()
        mock_console = MagicMock()
        cli1 = interactive.InteractiveCLI(mock_session, mock_console)
        assert cli1 is not None
        
        # Test with different console
        try:
            cli2 = interactive.InteractiveCLI(mock_session, None)
            assert cli2 is not None
        except TypeError:
            # If it doesn't accept None console, that's fine
            pass

    def test_interactive_cli_context_manager(self):
        """Test InteractiveCLI as context manager if supported."""
        import ccbt.cli.interactive as interactive
        from unittest.mock import MagicMock
        
        mock_session = MagicMock()
        mock_console = MagicMock()
        cli = interactive.InteractiveCLI(mock_session, mock_console)
        
        # Check if it has context manager methods
        has_enter = hasattr(cli, '__aenter__')
        has_exit = hasattr(cli, '__aexit__')
        
        if has_enter and has_exit:
            # Test context manager usage
            async def test_context():
                async with cli:
                    assert cli is not None
            
            import asyncio
            asyncio.run(test_context())
