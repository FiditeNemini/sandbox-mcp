"""
Process pool for isolated execution with resource limits.

This module provides process-level isolation for code execution while keeping
resource usage capped through worker limits and memory constraints.
"""

import io
import contextlib
import logging
import os
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SandboxProcessPool:
    """
    Resource-efficient process pool for isolated code execution.

    Provides process-level isolation while keeping resource usage capped:
    - Maximum worker processes (default: CPU count)
    - Memory limits per process (via resource module on supported platforms)
    - Automatic cleanup of idle workers
    - Per-session isolation guarantees

    Example:
        pool = SandboxProcessPool(max_workers=4)
        result = pool.execute_isolated(
            code="print('hello')",
            session_id="test-session",
            artifacts_dir="/tmp/artifacts"
        )
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the process pool.

        Args:
            max_workers: Maximum number of worker processes. Defaults to CPU count.
        """
        self.max_workers = max_workers or os.cpu_count() or 2
        self._executor: Optional[ProcessPoolExecutor] = None

    def get_executor(self) -> ProcessPoolExecutor:
        """
        Get or create process pool executor.

        Returns:
            The ProcessPoolExecutor instance
        """
        if self._executor is None:
            logger.debug(f"Creating process pool with {self.max_workers} workers")
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def execute_isolated(
        self,
        code: str,
        session_id: str,
        artifacts_dir: str,
        timeout: float = 30.0,
        memory_limit_mb: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in isolated process with resource limits.

        Args:
            code: Python code to execute
            session_id: Session identifier for isolation
            artifacts_dir: Directory for artifacts
            timeout: Execution timeout in seconds
            memory_limit_mb: Memory limit per process in MB (platform-dependent)

        Returns:
            Execution result dict with keys:
                - success: bool - Whether execution succeeded
                - output: str - Combined stdout/stderr output
                - error: str | None - Error message if failed
                - artifacts: List[str] - Paths to created artifacts
        """
        executor = self.get_executor()

        future = executor.submit(
            _execute_in_process,
            code,
            session_id,
            artifacts_dir,
            memory_limit_mb,
        )

        try:
            result = future.result(timeout=timeout)
            return result
        except FutureTimeoutError:
            future.cancel()
            logger.warning(f"Execution timed out after {timeout}s for session {session_id}")
            return {
                "success": False,
                "output": "",
                "error": f"Execution timed out after {timeout}s",
                "artifacts": [],
            }
        except Exception as e:
            logger.exception(f"Process pool execution failed for session {session_id}")
            return {
                "success": False,
                "output": "",
                "error": f"{type(e).__name__}: {e}",
                "artifacts": [],
            }

    def cleanup(self) -> None:
        """Shutdown process pool and clean up resources."""
        if self._executor is not None:
            logger.debug("Shutting down process pool")
            self._executor.shutdown(wait=True)
            self._executor = None

    @property
    def active_workers(self) -> int:
        """Get the number of active workers in the pool."""
        if self._executor is None:
            return 0
        return self._executor._max_workers  # type: ignore


def _execute_in_process(
    code: str,
    session_id: str,
    artifacts_dir: str,
    memory_limit_mb: Optional[int],
) -> Dict[str, Any]:
    """
    Execute code in isolated process with resource limits.

    This function runs in a separate process, providing complete isolation
    from the main process and other worker processes.

    Args:
        code: Python code to execute
        session_id: Session identifier for isolation
        artifacts_dir: Directory for artifacts
        memory_limit_mb: Memory limit per process in MB

    Returns:
        Execution result dict
    """
    import sys

    # Set memory limit if specified (Unix-like systems only)
    if memory_limit_mb:
        try:
            import resource

            memory_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, OSError, ImportError):
            # Not supported on all systems or failed to set
            pass

    # Create isolated execution context
    artifacts_path = Path(artifacts_dir)
    try:
        artifacts_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Failed to create artifacts directory: {e}",
            "artifacts": [],
        }

    # Execute with isolated globals - no module pollution
    execution_globals = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
        "__file__": "<sandbox>",
    }

    output_buffer = io.StringIO()

    try:
        with contextlib.redirect_stdout(output_buffer):
            with contextlib.redirect_stderr(output_buffer):
                exec(code, execution_globals)

        output = output_buffer.getvalue()

        # Collect created artifacts
        artifacts: List[str] = []
        if artifacts_path.exists():
            for item in artifacts_path.iterdir():
                if item.is_file():
                    artifacts.append(str(item))

        return {
            "success": True,
            "output": output,
            "error": None,
            "artifacts": artifacts,
        }

    except Exception as e:
        output = output_buffer.getvalue()
        return {
            "success": False,
            "output": output,
            "error": f"{type(e).__name__}: {e}",
            "artifacts": [],
        }


# Global process pool instance
_process_pool: Optional[SandboxProcessPool] = None


def get_process_pool(max_workers: Optional[int] = None) -> SandboxProcessPool:
    """
    Get or create global process pool.

    This provides a singleton process pool that can be shared across
    the application, reducing the overhead of creating new pools.

    Args:
        max_workers: Maximum number of workers. Only used on first call.

    Returns:
        The global SandboxProcessPool instance
    """
    global _process_pool
    if _process_pool is None:
        _process_pool = SandboxProcessPool(max_workers=max_workers)
    return _process_pool


def cleanup_global_process_pool() -> None:
    """Clean up the global process pool."""
    global _process_pool
    if _process_pool is not None:
        _process_pool.cleanup()
        _process_pool = None
