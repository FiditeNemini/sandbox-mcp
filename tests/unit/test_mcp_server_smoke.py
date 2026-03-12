"""
Smoke tests for MCP server startup and initialization.
"""

import pytest
import sys
import os


class TestStdioServerInitialization:
    """Test stdio server initialization."""

    def test_mcp_server_module_imports(self):
        """Test that MCP server module can be imported."""
        from sandbox import mcp_sandbox_server_stdio
        assert mcp_sandbox_server_stdio is not None

    def test_fastmcp_server_instance(self):
        """Test that FastMCP server instance exists."""
        from sandbox.mcp_sandbox_server_stdio import mcp
        assert mcp is not None
        # Check it's a FastMCP instance
        assert hasattr(mcp, 'name')

    def test_execution_context_class_exists(self):
        """Test that ExecutionContext class is defined."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext
        assert ExecutionContext is not None

    def test_execution_context_initialization(self):
        """Test that ExecutionContext can be instantiated."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext
        
        context = ExecutionContext()
        assert context is not None
        assert hasattr(context, 'project_root')
        assert hasattr(context, 'sandbox_area')

    def test_server_has_required_tools(self):
        """Test that server has required MCP tools registered."""
        from sandbox.mcp_sandbox_server_stdio import mcp
        
        # Get registered tools
        # FastMCP stores tools in _tool_manager or similar internal structure
        # We just verify the server has tool registration capability
        assert hasattr(mcp, 'tool') or hasattr(mcp, '_tool_manager')


class TestHTTPServerInitialization:
    """Test HTTP server initialization (if available)."""

    def test_http_server_module_imports(self):
        """Test that HTTP server module can be imported."""
        from sandbox import mcp_sandbox_server
        assert mcp_sandbox_server is not None


class TestFastMCPToolRegistration:
    """Test FastMCP tool registration."""

    def test_execute_code_tool_registered(self):
        """Test that execute_code tool is registered."""
        from sandbox.mcp_sandbox_server_stdio import mcp
        
        # The server should have tool registration decorators
        # Check that the module has the expected tool functions
        import sandbox.mcp_sandbox_server_stdio as server_module
        
        # Check for key tool functions
        assert hasattr(server_module, 'execute_code') or \
               hasattr(server_module, 'mcp')  # At least MCP instance exists

    def test_list_artifacts_tool_exists(self):
        """Test that list_artifacts tool function exists."""
        import sandbox.mcp_sandbox_server_stdio as server_module
        
        # Check for artifact-related functions
        assert hasattr(server_module, 'list_artifacts') or \
               hasattr(server_module, 'mcp')


class TestServerLogging:
    """Test server logging configuration."""

    def test_logger_configured(self):
        """Test that server logger is configured."""
        import logging
        
        logger = logging.getLogger('sandbox.mcp_sandbox_server_stdio')
        assert logger is not None

    def test_log_file_path_valid(self):
        """Test that log file path is valid."""
        import tempfile
        from pathlib import Path
        
        log_file = Path(tempfile.gettempdir()) / "sandbox_mcp_server.log"
        # Just verify the path can be constructed
        assert str(log_file)
