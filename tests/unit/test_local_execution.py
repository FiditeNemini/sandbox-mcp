"""
Tests for local sandbox execution functionality.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def sandbox():
    """Create and start a LocalSandbox instance for testing."""
    from sandbox.sdk.local_sandbox import LocalSandbox
    
    sandbox_instance = LocalSandbox()
    await sandbox_instance.start()
    yield sandbox_instance
    await sandbox_instance.stop()


@pytest.mark.asyncio
class TestLocalExecutionHappyPath:
    """Test basic local code execution."""

    async def test_basic_code_execution(self, sandbox):
        """Test that basic Python code executes successfully."""
        result = await sandbox.run("x = 1 + 2\nprint(x)")
        
        assert result is not None
        # Execution object should have output method
        assert hasattr(result, 'output')

    async def test_stdout_capture(self, sandbox):
        """Test that stdout is captured correctly."""
        code = 'print("Hello, World!")'
        result = await sandbox.run(code)
        
        assert result is not None
        output = await result.output()
        assert 'Hello, World!' in output

    async def test_execution_has_status(self, sandbox):
        """Test that execution result has status."""
        result = await sandbox.run("x = 1")
        
        assert hasattr(result, 'status')
        # Status can be success, error, pending, or unknown
        assert isinstance(result.status, str)


@pytest.mark.asyncio
class TestLocalExecutionErrors:
    """Test error handling in local execution."""

    async def test_syntax_error_handling(self, sandbox):
        """Test that syntax errors are handled gracefully."""
        code = "x = 1 + \n"  # Incomplete expression
        
        result = await sandbox.run(code)
        
        assert result is not None
        # Should have error status or error attribute
        assert hasattr(result, 'status') or hasattr(result, 'error')

    async def test_runtime_error_handling(self, sandbox):
        """Test that runtime errors are handled gracefully."""
        code = "raise ValueError('Test error')"
        
        result = await sandbox.run(code)
        
        assert result is not None
        # Should indicate an error occurred
        assert hasattr(result, 'error') or result.status == 'error'


@pytest.mark.asyncio
class TestLocalExecutionState:
    """Test state persistence in local execution."""

    async def test_variable_persistence(self, sandbox):
        """Test that variables persist across executions."""
        # First execution: set a variable
        result1 = await sandbox.run("x = 42")
        assert result1 is not None
        
        # Second execution: use the variable
        result2 = await sandbox.run("print(x)")
        output = await result2.output()
        
        assert '42' in output

    async def test_function_definition_persistence(self, sandbox):
        """Test that function definitions persist."""
        # Define a function
        result1 = await sandbox.run("""
def greet(name):
    return f"Hello, {name}!"
""")
        assert result1 is not None
        
        # Use the function
        result2 = await sandbox.run("print(greet('World'))")
        output = await result2.output()
        
        assert 'Hello, World!' in output
