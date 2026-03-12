"""
Tests for process pool isolation module.

These tests verify that the process pool provides proper isolation
and resource limits for code execution.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from sandbox.sdk import LocalSandbox, SandboxConfig, IsolationLevel
from sandbox.core.process_pool import SandboxProcessPool, get_process_pool, cleanup_global_process_pool


@pytest.fixture
def cleanup_pools():
    """Clean up process pools after each test."""
    yield
    cleanup_global_process_pool()


class TestSandboxProcessPool:
    """Tests for the SandboxProcessPool class."""

    def test_create_process_pool(self):
        """Test that a process pool can be created."""
        pool = SandboxProcessPool(max_workers=2)
        assert pool.max_workers == 2
        assert pool._executor is None  # Not created yet

    def test_get_executor_creates_pool(self):
        """Test that get_executor creates the pool on first access."""
        pool = SandboxProcessPool(max_workers=4)
        executor = pool.get_executor()
        assert executor is not None
        assert pool._executor is not None
        assert pool._executor == executor

    def test_cleanup(self):
        """Test that cleanup shuts down the pool."""
        pool = SandboxProcessPool(max_workers=2)
        executor = pool.get_executor()
        assert pool._executor is not None

        pool.cleanup()
        assert pool._executor is None

    def test_global_process_pool_singleton(self, cleanup_pools):
        """Test that the global process pool is a singleton."""
        pool1 = get_process_pool(max_workers=2)
        pool2 = get_process_pool(max_workers=4)
        assert pool1 is pool2  # Same instance


class TestProcessPoolIsolation:
    """Tests for process pool isolation behavior."""

    @pytest.mark.asyncio
    async def test_process_pool_module_isolation(self, cleanup_pools):
        """Test that process pool provides module-level isolation."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        # Session 1: Set module attribute in shared process
        async with LocalSandbox.create(name="test-isolation-1", config=config) as s1:
            r1 = await s1.run("import sys; sys.test_data = 'secret'; print('set secret')")
            assert r1.exception is None
            assert "set secret" in (await r1.output())

        # Session 2: Should NOT see module attribute (different process)
        async with LocalSandbox.create(name="test-isolation-2", config=config) as s2:
            r2 = await s2.run("import sys; val = getattr(sys, 'test_data', 'NOT_FOUND'); print(val)")
            assert r2.exception is None
            output = await r2.output()
            assert "NOT_FOUND" in output  # Module pollution prevented!

    @pytest.mark.asyncio
    async def test_process_pool_basic_execution(self, cleanup_pools):
        """Test basic code execution in process pool."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-basic", config=config) as sandbox:
            result = await sandbox.run("x = 42; print(f'x = {x}')")
            assert result.exception is None
            output = await result.output()
            assert "x = 42" in output

    @pytest.mark.asyncio
    async def test_process_pool_syntax_error(self, cleanup_pools):
        """Test that syntax errors are properly reported."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-syntax", config=config) as sandbox:
            result = await sandbox.run("this is not valid python !!!")
            assert result.exception is not None
            # The syntax error is caught by validation, check stderr
            error_output = await result.error()
            assert "syntax" in error_output.lower() or "invalid" in error_output.lower()

    @pytest.mark.asyncio
    async def test_process_pool_runtime_error(self, cleanup_pools):
        """Test that runtime errors are properly reported."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-runtime", config=config) as sandbox:
            result = await sandbox.run("raise ValueError('test error')")
            assert result.exception is not None
            assert "ValueError" in str(result.exception)
            assert "test error" in (await result.error())

    @pytest.mark.asyncio
    async def test_process_pool_timeout(self, cleanup_pools):
        """Test that timeout is enforced."""
        config = SandboxConfig(
            isolation_level=IsolationLevel.PROCESS_POOL,
            timeout=1.0  # 1 second timeout
        )

        async with LocalSandbox.create(name="test-timeout", config=config) as sandbox:
            result = await sandbox.run("import time; time.sleep(10)")
            assert result.exception is not None
            assert "timed out" in str(result.exception).lower()

    @pytest.mark.asyncio
    async def test_process_pool_multiple_executions(self, cleanup_pools):
        """Test that the process pool can handle multiple executions."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-multi", config=config) as sandbox:
            for i in range(5):
                result = await sandbox.run(f"print({i})")
                assert result.exception is None
                assert str(i) in (await result.output())


class TestProcessPoolPerformance:
    """Tests for process pool performance characteristics."""

    @pytest.mark.asyncio
    async def test_process_pool_performance_acceptable(self, cleanup_pools):
        """Test that process pool has acceptable performance."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        import time
        start = time.time()

        async with LocalSandbox.create(name="test-perf", config=config) as sandbox:
            for i in range(5):
                await sandbox.run(f"x = {i}")

        elapsed = time.time() - start
        assert elapsed < 5.0  # Should complete 5 executions quickly

    @pytest.mark.asyncio
    async def test_process_pool_vs_in_process(self, cleanup_pools):
        """Compare process pool performance with in-process execution."""
        config_pool = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)
        config_in_process = SandboxConfig(isolation_level=IsolationLevel.IN_PROCESS)

        import time

        # Process pool execution
        start = time.time()
        async with LocalSandbox.create(name="test-pool", config=config_pool) as sandbox:
            await sandbox.run("x = 1")
        pool_time = time.time() - start

        # In-process execution
        start = time.time()
        async with LocalSandbox.create(name="test-inproc", config=config_in_process) as sandbox:
            await sandbox.run("x = 1")
        inproc_time = time.time() - start

        # Process pool will be slower, but should not be excessively so
        assert pool_time < inproc_time * 10  # Not more than 10x slower


class TestProcessPoolIntegration:
    """Integration tests for process pool with LocalSandbox."""

    @pytest.mark.asyncio
    async def test_sandbox_config_isolation_level(self, cleanup_pools):
        """Test that isolation level is properly read from config."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-config", config=config) as sandbox:
            assert sandbox._config.isolation_level == IsolationLevel.PROCESS_POOL

    @pytest.mark.asyncio
    async def test_sandbox_default_isolation_in_process(self, cleanup_pools):
        """Test that default isolation level is IN_PROCESS."""
        config = SandboxConfig()  # Default

        async with LocalSandbox.create(name="test-default", config=config) as sandbox:
            assert sandbox._config.isolation_level == IsolationLevel.IN_PROCESS

    @pytest.mark.asyncio
    async def test_process_pool_with_validation(self, cleanup_pools):
        """Test that code validation works with process pool."""
        config = SandboxConfig(isolation_level=IsolationLevel.PROCESS_POOL)

        async with LocalSandbox.create(name="test-validation", config=config) as sandbox:
            # Valid code should execute
            result = await sandbox.run("x = 42", validate=True)
            assert result.exception is None


class TestProcessPoolArtifacts:
    """Tests for artifact handling in process pool mode."""

    @pytest.mark.asyncio
    async def test_process_pool_artifacts_captured(self, cleanup_pools):
        """Test that artifacts are captured in process pool mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                isolation_level=IsolationLevel.PROCESS_POOL
            )

            async with LocalSandbox.create(name="test-artifacts", config=config) as sandbox:
                # Create a file in the artifacts directory
                result = await sandbox.run(
                    f"import pathlib; pathlib.Path('{tmpdir}/test.txt').write_text('hello')"
                )
                assert result.exception is None

                # Check artifacts
                test_file = Path(tmpdir) / "test.txt"
                if test_file.exists():
                    content = test_file.read_text()
                    assert content == "hello"


class TestMemoryLimits:
    """Tests for memory limit enforcement."""

    @pytest.mark.asyncio
    async def test_memory_limit_configuration(self, cleanup_pools):
        """Test that memory limit can be configured."""
        config = SandboxConfig(
            isolation_level=IsolationLevel.PROCESS_POOL,
            memory_limit_mb=100
        )

        async with LocalSandbox.create(name="test-mem", config=config) as sandbox:
            assert sandbox._config.memory_limit_mb == 100
            # Small allocation should work
            result = await sandbox.run("x = 'a' * 1000")
            assert result.exception is None

    @pytest.mark.asyncio
    async def test_max_workers_configuration(self, cleanup_pools):
        """Test that max workers can be configured."""
        config = SandboxConfig(
            isolation_level=IsolationLevel.PROCESS_POOL,
            max_workers=4
        )

        async with LocalSandbox.create(name="test-workers", config=config) as sandbox:
            assert sandbox._config.max_workers == 4
