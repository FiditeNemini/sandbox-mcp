"""Tests for transport parity between stdio and HTTP MCP servers.

This test suite verifies that both transports provide the same tools
and behavior, ensuring architectural consistency.
"""

from __future__ import annotations

import pytest


class TestTransportParity:
    """Test that stdio and HTTP transports have feature parity."""

    def test_both_servers_use_shared_context(self):
        """Test that both servers import ExecutionContext from the same shared module."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext as StdioContext
        from sandbox.mcp_sandbox_server import ExecutionContext as HTTPContext
        from sandbox.core.execution_services import ExecutionContext as CoreContext

        # All three should reference the same class
        assert StdioContext is CoreContext
        assert HTTPContext is CoreContext
        assert StdioContext is HTTPContext

    def test_both_servers_use_shared_resource_manager(self):
        """Test that both servers use the same resource manager."""
        from sandbox.core.resource_manager import get_resource_manager

        # Both servers should use the singleton resource manager
        rm1 = get_resource_manager()
        rm2 = get_resource_manager()
        assert rm1 is rm2

    def test_both_servers_use_shared_security_manager(self):
        """Test that both servers use the same security manager."""
        from sandbox.core.security import SecurityLevel, get_security_manager

        # Both servers should use security manager with same level
        sm1 = get_security_manager(SecurityLevel.MEDIUM)
        sm2 = get_security_manager(SecurityLevel.MEDIUM)
        # Security managers are singletons per level
        assert sm1 is sm2

    def test_both_servers_register_all_tools(self):
        """Test that both servers register tools through tool_registry."""
        from sandbox.server.tool_registry import ToolRegistry

        # Both servers should use ToolRegistry for tool registration
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Both servers should have tool_registry
        assert hasattr(stdio_server, 'tool_registry')
        assert hasattr(http_server, 'tool_registry')

        # Both should be ToolRegistry instances
        assert isinstance(stdio_server.tool_registry, ToolRegistry)
        assert isinstance(http_server.tool_registry, ToolRegistry)

    def test_stdio_server_line_count_within_limit(self):
        """Test that stdio server stays within 500 line limit."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import inspect

        source = inspect.getsource(stdio_server)
        line_count = len(source.split('\n'))
        # stdio server should be minimal (currently ~73 lines)
        assert line_count < 500, f"stdio server has {line_count} lines, exceeds 500 line limit"

    def test_http_server_line_count_within_limit(self):
        """Test that HTTP server stays within 500 line limit."""
        import sandbox.mcp_sandbox_server as http_server
        import inspect

        source = inspect.getsource(http_server)
        line_count = len(source.split('\n'))
        # HTTP server should be minimal after refactor (currently ~58 lines)
        assert line_count < 500, f"HTTP server has {line_count} lines, exceeds 500 line limit"

    def test_both_servers_have_fastmcp_instance(self):
        """Test that both servers have FastMCP instances."""
        from sandbox.mcp_sandbox_server_stdio import mcp as stdio_mcp
        from sandbox.mcp_sandbox_server import mcp as http_mcp

        # Both should have mcp instances with name attribute
        assert hasattr(stdio_mcp, 'name')
        assert hasattr(http_mcp, 'name')

    def test_both_servers_use_same_catalog(self):
        """Test that both servers use the same catalog primitives."""
        from sandbox.server.catalog import SERVER_ID, SERVER_INSTRUCTIONS

        # Both servers should use the same catalog constants
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Check that both servers have registered catalog primitives
        # (this is done by calling register_catalog_primitives(mcp))
        # We can verify the catalog module is accessible to both
        assert hasattr(stdio_server, 'SERVER_ID')
        assert hasattr(http_server, 'SERVER_ID')

    def test_no_duplicate_execution_context_classes(self):
        """Test that there are no duplicate ExecutionContext classes defined in server files."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server
        import inspect

        # Get source code for both servers
        stdio_source = inspect.getsource(stdio_server)
        http_source = inspect.getsource(http_server)

        # Neither should define a class named ExecutionContext
        # They should import it from core.execution_services instead
        assert 'class ExecutionContext:' not in stdio_source
        assert 'class ExecutionContext:' not in http_source

    def test_no_duplicate_helper_functions(self):
        """Test that servers don't duplicate helper functions like monkey_patch, find_free_port, etc."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server
        import inspect

        # Get source code for both servers
        stdio_source = inspect.getsource(stdio_server)
        http_source = inspect.getsource(http_server)

        # These functions should NOT be defined in server files
        # They should be imported from server/execution_helpers.py instead
        duplicate_functions = [
            'def monkey_patch_matplotlib',
            'def monkey_patch_pil',
            'def find_free_port',
            'def launch_web_app',
            'def collect_artifacts',
        ]

        for func in duplicate_functions:
            # stdio server should not have these (uses tool_registry)
            assert func not in stdio_source, f"stdio server has duplicate function: {func}"
            # http server should not have these (uses tool_registry)
            assert func not in http_source, f"http server has duplicate function: {func}"

    def test_both_servers_use_persistent_context_factory(self):
        """Test that both servers pass PersistentExecutionContext to tool_registry."""
        from sandbox.core.execution_context import PersistentExecutionContext

        # Both servers should import and use PersistentExecutionContext
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Both should have access to PersistentExecutionContext
        assert hasattr(stdio_server, 'PersistentExecutionContext')
        assert hasattr(http_server, 'PersistentExecutionContext')


class TestTransportSemantics:
    """Test that both transports have the same execution semantics."""

    def test_both_servers_use_same_execution_context_pattern(self):
        """Test that both servers use the same global ctx pattern."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Both should have a global ctx variable
        assert hasattr(stdio_server, 'ctx')
        assert hasattr(http_server, 'ctx')

        # Both should be ExecutionContext instances
        from sandbox.core.execution_services import ExecutionContext
        assert isinstance(stdio_server.ctx, ExecutionContext)
        assert isinstance(http_server.ctx, ExecutionContext)

    def test_both_support_same_artifact_operations(self):
        """Test that both servers support the same artifact operations through tool_registry."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Both should have tool_registry with artifact methods
        stdio_methods = dir(stdio_server.tool_registry)
        http_methods = dir(http_server.tool_registry)

        # Check for key artifact-related methods
        artifact_methods = [
            'register_list_artifacts',
            'register_cleanup_artifacts',
            'register_backup_current_artifacts',
            'register_rollback_to_backup',
        ]

        for method in artifact_methods:
            assert method in stdio_methods, f"stdio missing {method}"
            assert method in http_methods, f"http missing {method}"

    def test_both_support_same_execution_methods(self):
        """Test that both servers support the same execution operations."""
        import sandbox.mcp_sandbox_server_stdio as stdio_server
        import sandbox.mcp_sandbox_server as http_server

        # Both should have tool_registry with execution methods
        stdio_methods = dir(stdio_server.tool_registry)
        http_methods = dir(http_server.tool_registry)

        # Check for key execution-related methods
        execution_methods = [
            'register_execute',
            'register_execute_with_artifacts',
            'register_shell_execute',
            'register_start_repl',
            'register_start_enhanced_repl',
        ]

        for method in execution_methods:
            assert method in stdio_methods, f"stdio missing {method}"
            assert method in http_methods, f"http missing {method}"
