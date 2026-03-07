"""
Smoke tests for package import functionality.

These tests verify that the sandbox package and its main submodules
can be imported successfully.
"""

import pytest


class TestPackageImportSmoke:
    """Smoke tests for basic package imports."""

    def test_import_sandbox(self):
        """Test that the main sandbox package can be imported."""
        import sandbox
        assert sandbox is not None

    def test_import_sandbox_core(self):
        """Test that sandbox.core submodule can be imported."""
        from sandbox import core
        assert core is not None

    def test_import_sandbox_sdk(self):
        """Test that sandbox.sdk submodule can be imported."""
        from sandbox import sdk
        assert sdk is not None

    def test_import_sandbox_server(self):
        """Test that sandbox.server submodule can be imported."""
        from sandbox import server
        assert server is not None

    def test_import_sandbox_utils(self):
        """Test that sandbox.utils submodule can be imported."""
        from sandbox import utils
        assert utils is not None


class TestMainSubmodulesImport:
    """Test that all main submodules are importable."""

    def test_code_validator_import(self):
        """Test CodeValidator can be imported."""
        from sandbox.core.code_validator import CodeValidator
        assert CodeValidator is not None

    def test_execution_context_import(self):
        """Test execution_context module can be imported."""
        from sandbox.core import execution_context
        assert execution_context is not None
        # Verify the main class is available
        assert hasattr(execution_context, 'PersistentExecutionContext')

    def test_security_import(self):
        """Test SecurityManager can be imported."""
        from sandbox.core.security import SecurityManager
        assert SecurityManager is not None

    def test_resource_manager_import(self):
        """Test ResourceManager can be imported."""
        from sandbox.core.resource_manager import ResourceManager
        assert ResourceManager is not None

    def test_base_sandbox_import(self):
        """Test BaseSandbox can be imported."""
        from sandbox.sdk.base_sandbox import BaseSandbox
        assert BaseSandbox is not None

    def test_execution_import(self):
        """Test execution module can be imported."""
        from sandbox.sdk import execution
        assert execution is not None

    def test_local_sandbox_import(self):
        """Test LocalSandbox can be imported."""
        from sandbox.sdk.local_sandbox import LocalSandbox
        assert LocalSandbox is not None


class TestPackageVersion:
    """Test package version consistency."""

    def test_version_attribute_exists(self):
        """Test that package has a version attribute."""
        import sandbox
        assert hasattr(sandbox, '__version__')

    def test_version_is_string(self):
        """Test that version is a non-empty string."""
        import sandbox
        assert isinstance(sandbox.__version__, str)
        assert len(sandbox.__version__) > 0

    def test_version_consistency(self):
        """Test that version is consistent across modules."""
        import sandbox
        from sandbox import sdk
        
        # Both should have the same version
        assert sandbox.__version__ == sdk.__version__
