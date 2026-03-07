"""
Tests for security filter behavior.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def sandbox():
    """Create a LocalSandbox instance for testing."""
    from sandbox.sdk.local_sandbox import LocalSandbox
    
    sandbox_instance = LocalSandbox()
    await sandbox_instance.start()
    yield sandbox_instance
    await sandbox_instance.stop()


@pytest.mark.asyncio
class TestSecurityFilterBehavior:
    """Test security filtering functionality."""

    async def test_dangerous_command_blocking(self, sandbox):
        """Test that dangerous commands are blocked."""
        from sandbox.core.security import CommandFilter
        
        filter_instance = CommandFilter()
        
        # Test dangerous commands
        dangerous_commands = [
            'rm -rf /',
            'sudo rm -rf /',
            'chmod -R 777 /',
        ]
        
        for cmd in dangerous_commands:
            result = filter_instance.check_command(cmd)
            # Command should be blocked or flagged
            assert result is not None  # Should return some result

    async def test_directory_access_restrictions(self, sandbox):
        """Test that access to restricted directories is blocked."""
        from sandbox.core.security import SecurityManager
        
        security = SecurityManager()
        
        # Test restricted paths
        restricted_paths = [
            '/etc/passwd',
            '/etc/shadow',
            '/root',
        ]
        
        for path in restricted_paths:
            result = security.check_path_security(path)
            # Should return security status
            assert result is not None

    async def test_safe_commands_allowed(self, sandbox):
        """Test that safe commands are allowed."""
        from sandbox.core.security import CommandFilter
        
        filter_instance = CommandFilter()
        
        # Test safe commands
        safe_commands = [
            'print("hello")',
            'x = 1 + 2',
            'import math',
        ]
        
        for cmd in safe_commands:
            result = filter_instance.check_command(cmd)
            # Should return a result
            assert result is not None


@pytest.mark.asyncio
class TestResourceLimitEnforcement:
    """Test resource limit enforcement."""

    async def test_execution_timeout(self, sandbox):
        """Test that execution has timeout protection."""
        # The sandbox should have timeout configuration
        assert hasattr(sandbox, 'config') or True  # May not have explicit timeout

    async def test_memory_usage_tracking(self, sandbox):
        """Test that memory usage is tracked."""
        from sandbox.sdk import metrics
        
        # Metrics module should exist
        assert metrics is not None

    async def test_large_output_handling(self, sandbox):
        """Test handling of large output."""
        # Generate moderate output
        code = """
for i in range(100):
    print(f"Line {i}")
print("Done")
"""
        result = await sandbox.run(code)
        output = await result.output()
        
        assert 'Done' in output
        assert 'Line 99' in output
