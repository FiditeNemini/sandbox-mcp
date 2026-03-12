"""
Tests for optional dependency extras.

These tests verify that optional features can be imported when their
dependencies are installed, and gracefully fail when not available.
"""

import pytest


class TestWebExtras:
    """Test web-related optional dependencies."""

    def test_flask_available_when_web_extra_installed(self):
        """Test that Flask can be imported (web extra)."""
        try:
            from flask import Flask
            assert Flask is not None
        except ImportError:
            # Flask is optional, skip if not installed
            pytest.skip("Flask not installed (web extra)")

    def test_streamlit_available_when_web_extra_installed(self):
        """Test that Streamlit can be imported (web extra)."""
        try:
            import streamlit as st
            assert st is not None
        except ImportError:
            # Streamlit is optional, skip if not installed
            pytest.skip("Streamlit not installed (web extra)")


class TestCoreWithoutWebExtras:
    """Test that core functionality works without web extras."""

    def test_sandbox_imports_without_flask(self):
        """Test that sandbox core imports without Flask."""
        # This should work even if Flask is not installed
        import sandbox
        assert sandbox is not None

    def test_code_validator_without_web_extras(self):
        """Test CodeValidator works without web dependencies."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        result = validator.validate_and_format("x = 1")
        
        assert result['valid'] is True

    def test_local_sandbox_without_web_extras(self):
        """Test LocalSandbox can be instantiated without web deps."""
        from sandbox.sdk.local_sandbox import LocalSandbox
        
        sandbox_instance = LocalSandbox()
        assert sandbox_instance is not None


class TestDevExtras:
    """Test development-related optional dependencies."""

    def test_pytest_available(self):
        """Test that pytest is available (dev extra)."""
        import pytest
        assert pytest is not None

    def test_black_available_when_dev_extra_installed(self):
        """Test that black can be imported (dev extra)."""
        try:
            import black
            assert black is not None
        except ImportError:
            # Black is optional dev dependency
            pytest.skip("Black not installed (dev extra)")

    def test_mypy_available_when_dev_extra_installed(self):
        """Test that mypy can be imported (dev extra)."""
        try:
            import mypy
            assert mypy is not None
        except ImportError:
            # Mypy is optional dev dependency
            pytest.skip("Mypy not installed (dev extra)")
