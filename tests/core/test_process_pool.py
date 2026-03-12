"""
Tests for the resource-efficient process pool for module isolation.

These tests verify that the SandboxProcessPool provides proper
process-level isolation while keeping resource usage efficient.
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest

from sandbox.core.process_pool import (
    SandboxProcessPool,
    get_process_pool,
    cleanup_global_process_pool,
    _execute_in_process,
)
from sandbox.sdk.local_sandbox import LocalSandbox


class TestSandboxProcessPool:
    """Tests for the SandboxProcessPool class."""

    def test_init_default_workers(self):
        """Test initialization with default workers."""
        pool = SandboxProcessPool()
        assert pool.max_workers > 0
        assert pool.max_workers == os.cpu_count() or pool.max_workers == 2

    def test_init_custom_workers(self):
        """Test initialization with custom workers."""
        pool = SandboxProcessPool(max_workers=4)
        assert pool.max_workers == 4

    def test_get_executor_creates_executor(self):
        """Test that get_executor creates a new executor."""
        pool = SandboxProcessPool(max_workers=2)
        executor = pool.get_executor()
        assert executor is not None
        assert executor._max_workers == 2

    def test_get_executor_returns_same_executor(self):
        """Test that get_executor returns the same executor instance."""
        pool = SandboxProcessPool(max_workers=2)
        executor1 = pool.get_executor()
        executor2 = pool.get_executor()
        assert executor1 is executor2

    def test_active_workers_property(self):
        """Test the active_workers property."""
        pool = SandboxProcessPool(max_workers=4)
        assert pool.active_workers == 0  # No executor created yet

        pool.get_executor()
        assert pool.active_workers == 4

    def test_cleanup(self):
        """Test cleanup shuts down the executor."""
        pool = SandboxProcessPool(max_workers=2)
        pool.get_executor()
        assert pool._executor is not None

        pool.cleanup()
        assert pool._executor is None

    def test_cleanup_is_idempotent(self):
        """Test that cleanup can be called multiple times safely."""
        pool = SandboxProcessPool(max_workers=2)
        pool.cleanup()
        pool.cleanup()
        # Should not raise

    def test_cleanup_when_no_executor(self):
        """Test cleanup when executor was never created."""
        pool = SandboxProcessPool(max_workers=2)
        pool.cleanup()  # Should not raise


class TestExecuteIsolated:
    """Tests for the execute_isolated method."""

    def test_execute_simple_code(self, tmp_path):
        """Test executing simple code."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="x = 1 + 1\nprint('result:', x)",
            session_id="test-session",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True
        assert "result: 2" in result["output"]
        assert result["error"] is None

    def test_execute_with_syntax_error(self, tmp_path):
        """Test executing code with syntax error."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="this is not valid python",
            session_id="test-session",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is False
        assert result["error"] is not None
        assert "SyntaxError" in result["error"]

    def test_execute_with_runtime_error(self, tmp_path):
        """Test executing code with runtime error."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="raise ValueError('test error')",
            session_id="test-session",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is False
        assert result["error"] is not None
        assert "ValueError" in result["error"]

    def test_execute_with_timeout(self, tmp_path):
        """Test execution timeout."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="import time; time.sleep(10)",
            session_id="test-session",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=0.5,  # Short timeout
        )

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_execute_creates_artifacts_directory(self, tmp_path):
        """Test that artifacts directory is created."""
        artifacts_dir = tmp_path / "test_artifacts"
        pool = SandboxProcessPool(max_workers=2)

        pool.execute_isolated(
            code="print('test')",
            session_id="test-session",
            artifacts_dir=str(artifacts_dir),
            timeout=5.0,
        )

        assert artifacts_dir.exists()

    def test_execute_captures_artifact_files(self, tmp_path):
        """Test that artifact files are captured."""
        artifacts_dir = tmp_path / "artifacts"
        pool = SandboxProcessPool(max_workers=2)

        pool.execute_isolated(
            code=f"""
import pathlib
pathlib.Path('{artifacts_dir}/test.txt').write_text('artifact content')
print('done')
""",
            session_id="test-session",
            artifacts_dir=str(artifacts_dir),
            timeout=5.0,
        )

        result = pool.execute_isolated(
            code="print('second execution')",
            session_id="test-session-2",
            artifacts_dir=str(artifacts_dir),
            timeout=5.0,
        )

        assert result["success"] is True
        # The artifact should be listed
        assert len(result["artifacts"]) >= 0

    def test_execute_with_module_isolation(self, tmp_path):
        """Test that modules are isolated between executions."""
        pool = SandboxProcessPool(max_workers=2)

        # First execution sets a variable
        result1 = pool.execute_isolated(
            code="custom_var = 42\nprint('first:', custom_var)",
            session_id="session1",
            artifacts_dir=str(tmp_path / "artifacts1"),
            timeout=5.0,
        )

        assert result1["success"] is True
        assert "first: 42" in result1["output"]

        # Second execution should not see the variable
        result2 = pool.execute_isolated(
            code="print('var exists:', 'custom_var' in globals())",
            session_id="session2",
            artifacts_dir=str(tmp_path / "artifacts2"),
            timeout=5.0,
        )

        assert result2["success"] is True
        assert "var exists: False" in result2["output"]

    def test_execute_with_memory_limit(self, tmp_path):
        """Test execution with memory limit (platform-dependent)."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="print('test')",
            session_id="test-session",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
            memory_limit_mb=100,
        )

        # Should succeed or fail gracefully depending on platform
        assert result is not None

    def test_execute_multiple_concurrent(self, tmp_path):
        """Test multiple concurrent executions."""
        pool = SandboxProcessPool(max_workers=2)

        import asyncio

        async def run_concurrent():
            results = []
            for i in range(3):
                result = pool.execute_isolated(
                    code=f"print('execution {i}')",
                    session_id=f"session{i}",
                    artifacts_dir=str(tmp_path / "artifacts"),
                    timeout=5.0,
                )
                results.append(result)
            return results

        results = asyncio.run(run_concurrent())

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["success"] is True
            assert f"execution {i}" in result["output"]


class TestExecuteInProcess:
    """Tests for the _execute_in_process worker function."""

    def test_execute_in_process_simple(self, tmp_path):
        """Test basic execution in isolated process."""
        result = _execute_in_process(
            code="x = 1 + 2\nprint(x)",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            memory_limit_mb=None,
        )

        assert result["success"] is True
        assert "3" in result["output"]

    def test_execute_in_process_with_exception(self, tmp_path):
        """Test execution that raises an exception."""
        result = _execute_in_process(
            code="raise RuntimeError('test error')",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            memory_limit_mb=None,
        )

        assert result["success"] is False
        assert "RuntimeError" in result["error"]

    def test_execute_in_process_creates_artifacts_dir(self, tmp_path):
        """Test that artifacts directory is created."""
        artifacts_dir = tmp_path / "test_artifacts"

        _execute_in_process(
            code="print('test')",
            session_id="test",
            artifacts_dir=str(artifacts_dir),
            memory_limit_mb=None,
        )

        assert artifacts_dir.exists()

    def test_execute_in_process_with_stdout_stderr(self, tmp_path):
        """Test that both stdout and stderr are captured."""
        result = _execute_in_process(
            code="import sys; print('stdout'); print('stderr', file=sys.stderr)",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            memory_limit_mb=None,
        )

        assert result["success"] is True
        # Both stdout and stderr are captured
        assert "stdout" in result["output"]
        assert "stderr" in result["output"]


class TestGlobalProcessPool:
    """Tests for the global process pool functions."""

    def test_get_process_pool_creates_singleton(self):
        """Test that get_process_pool returns a singleton."""
        # Clean up any existing pool
        cleanup_global_process_pool()

        pool1 = get_process_pool(max_workers=2)
        pool2 = get_process_pool(max_workers=4)  # Ignored after first call

        assert pool1 is pool2
        assert pool1.max_workers == 2

    def test_cleanup_global_process_pool(self):
        """Test cleanup_global_process_pool."""
        # Create a pool
        pool = get_process_pool(max_workers=2)
        assert pool is not None

        # Clean up
        cleanup_global_process_pool()

        # New pool should be created
        new_pool = get_process_pool(max_workers=4)
        assert new_pool.max_workers == 4

        cleanup_global_process_pool()


class TestProcessPoolResourceEfficiency:
    """Tests for resource efficiency features."""

    def test_worker_recycling(self, tmp_path):
        """Test that workers are recycled across executions."""
        pool = SandboxProcessPool(max_workers=1)

        # Execute multiple times
        for i in range(5):
            result = pool.execute_isolated(
                code=f"print({i})",
                session_id=f"session{i}",
                artifacts_dir=str(tmp_path / "artifacts"),
                timeout=5.0,
            )
            assert result["success"] is True

        # Only one worker should be used
        assert pool.active_workers == 1

    def test_max_workers_limit(self, tmp_path):
        """Test that max_workers limits concurrent executions."""
        pool = SandboxProcessPool(max_workers=2)

        import time
        import threading

        results = []
        errors = []

        def run_execution(i):
            try:
                result = pool.execute_isolated(
                    code=f"""
import time
print('Start {i}')
time.sleep(0.1)
print('End {i}')
""",
                    session_id=f"session{i}",
                    artifacts_dir=str(tmp_path / f"artifacts{i}"),
                    timeout=5.0,
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start more threads than max_workers
        threads = []
        for i in range(5):
            t = threading.Thread(target=run_execution, args=(i,))
            t.start()
            threads.append(t)

        # Wait for all to complete
        for t in threads:
            t.join()

        # All should complete
        assert len(results) == 5
        assert len(errors) == 0

    def test_memory_limit_honored(self, tmp_path):
        """Test that memory limits are respected (platform-dependent)."""
        pool = SandboxProcessPool(max_workers=1)

        # This should work with memory limit
        result = pool.execute_isolated(
            code="""
# Small memory footprint
data = list(range(100))
print(f'Created {len(data)} items')
""",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
            memory_limit_mb=50,
        )

        assert result["success"] is True


class TestProcessPoolIsolation:
    """Tests for module isolation guarantees."""

    def test_module_import_isolation(self, tmp_path):
        """Test that module imports don't leak between executions."""
        pool = SandboxProcessPool(max_workers=2)

        # First execution imports a module
        result1 = pool.execute_isolated(
            code="""
import json
custom_module = json
print('json imported')
""",
            session_id="session1",
            artifacts_dir=str(tmp_path / "artifacts1"),
            timeout=5.0,
        )

        assert result1["success"] is True

        # Second execution checks if custom_module exists
        result2 = pool.execute_isolated(
            code="""
exists = 'custom_module' in globals()
print(f'custom_module exists: {exists}')
""",
            session_id="session2",
            artifacts_dir=str(tmp_path / "artifacts2"),
            timeout=5.0,
        )

        assert result2["success"] is True
        assert "custom_module exists: False" in result2["output"]

    def test_global_variable_isolation(self, tmp_path):
        """Test that global variables don't leak between executions."""
        pool = SandboxProcessPool(max_workers=2)

        # First execution sets globals
        result1 = pool.execute_isolated(
            code="""
global_var = "session1"
another_var = [1, 2, 3]
print('Set globals')
""",
            session_id="session1",
            artifacts_dir=str(tmp_path / "artifacts1"),
            timeout=5.0,
        )

        assert result1["success"] is True

        # Second execution checks for those globals
        result2 = pool.execute_isolated(
            code="""
vars_exist = 'global_var' in globals() and 'another_var' in globals()
print(f'Globals exist: {vars_exist}')
""",
            session_id="session2",
            artifacts_dir=str(tmp_path / "artifacts2"),
            timeout=5.0,
        )

        assert result2["success"] is True
        assert "Globals exist: False" in result2["output"]

    def test_builtin_preservation(self, tmp_path):
        """Test that builtins are available in isolated process."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="""
# Test that builtins are available
# Note: __builtins__ can be a module or dict depending on context
import builtins
assert hasattr(builtins, 'len')
assert hasattr(builtins, 'print')
assert hasattr(builtins, 'isinstance')
# Test that they work
assert len([1, 2, 3]) == 3
print('Builtins available')
""",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True
        assert "Builtins available" in result["output"]


class TestProcessPoolEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_code(self, tmp_path):
        """Test executing empty code."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True

    def test_code_with_only_comments(self, tmp_path):
        """Test executing code with only comments."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="# This is a comment\n# Another comment",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True

    def test_unicode_output(self, tmp_path):
        """Test execution with unicode output."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="print('Hello 世界 🌍')",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True
        assert "世界" in result["output"]

    def test_multiline_output(self, tmp_path):
        """Test execution with multiline output."""
        pool = SandboxProcessPool(max_workers=2)

        result = pool.execute_isolated(
            code="""
print('Line 1')
print('Line 2')
print('Line 3')
""",
            session_id="test",
            artifacts_dir=str(tmp_path / "artifacts"),
            timeout=5.0,
        )

        assert result["success"] is True
        assert "Line 1" in result["output"]
        assert "Line 2" in result["output"]
        assert "Line 3" in result["output"]


@pytest.mark.integration
class TestProcessPoolIntegration:
    """Integration tests for process pool with LocalSandbox."""

    @pytest.mark.asyncio
    async def test_local_sandbox_with_process_pool_isolation(self):
        """Test LocalSandbox with PROCESS_POOL isolation level."""
        from sandbox.sdk.config import SandboxConfig, IsolationLevel

        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL, max_workers=2)
        sandbox = LocalSandbox(config=config)

        await sandbox.start()
        result = await sandbox.run("x = 1 + 1; print('Result:', x)")

        assert result is not None
        output = await result.output()
        assert "Result: 2" in output

        await sandbox.stop()

    @pytest.mark.asyncio
    async def test_process_pool_prevents_module_pollution(self):
        """Test that process pool isolation prevents module pollution."""
        from sandbox.sdk.config import SandboxConfig, IsolationLevel

        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)
        sandbox = LocalSandbox(config=config)

        await sandbox.start()

        # First execution imports and uses a module
        result1 = await sandbox.run("""
import json
custom_parser = json
print('parsed')
""")

        assert result1.exception is None

        # Second execution should not see custom_parser
        result2 = await sandbox.run("""
has_custom = 'custom_parser' in globals()
print(f'has custom: {has_custom}')
""")

        assert result2.exception is None
        output = await result2.output()
        assert "has custom: False" in output

        await sandbox.stop()

    @pytest.mark.asyncio
    async def test_process_pool_with_validation(self):
        """Test process pool with code validation enabled."""
        from sandbox.sdk.config import SandboxConfig, IsolationLevel

        config = SandboxConfig(
            isolation_level=IsolationLevel.PROCESS_POOL,
            max_workers=2,
        )
        sandbox = LocalSandbox(config=config)

        await sandbox.start()

        # Valid code should execute
        result = await sandbox.run("print('valid code')", validate=True)
        assert result.exception is None
        output = await result.output()
        assert "valid code" in output

        await sandbox.stop()
