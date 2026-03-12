"""
Worktree Sandbox - Git worktree-based filesystem isolation.

This module provides a sandbox implementation that uses git worktrees
for complete filesystem isolation while maintaining merge capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from .base_sandbox import BaseSandbox
from .command import Command
from .execution import Execution
from .metrics import Metrics
from .config import SandboxConfig
from ..core.worktree_isolation import (
    WorktreeIsolationManager,
    WorktreeInfo,
    WorktreeStatus,
    get_worktree_manager,
    MergeConflictError,
)


logger = logging.getLogger(__name__)


class WorktreeSandbox(BaseSandbox):
    """
    Sandbox implementation using git worktree isolation.

    Provides complete filesystem isolation by creating a git worktree
    for each session. Changes can be merged back to the base branch.

    Example:
        from sandbox.sdk import WorktreeSandbox

        async with WorktreeSandbox.create(
            name="my-isolated-session",
            base_branch="main",
            auto_merge=True,
        ) as sandbox:
            # Execute code in isolated worktree
            result = await sandbox.run("print('Hello from worktree!')")

            # Make file changes
            await sandbox.run("open('new_file.py', 'w').write('# new file')")

            # On exit, changes are auto-merged to main branch
    """

    def __init__(
        self,
        name: str,
        project_root: Optional[Path] = None,
        base_branch: Optional[str] = None,
        auto_merge: bool = False,
        auto_cleanup: bool = True,
        worktrees_parent: Optional[Path] = None,
        config: Optional[SandboxConfig] = None,
    ):
        """
        Initialize a worktree sandbox.

        Args:
            name: Sandbox/session name
            project_root: Git repository root (defaults to current directory)
            base_branch: Base branch to create worktree from
            auto_merge: Auto-merge changes on close
            auto_cleanup: Auto-cleanup worktree on close
            worktrees_parent: Parent directory for worktrees
            config: Optional sandbox configuration
        """
        # Call BaseSandbox constructor with required parameters
        # WorktreeSandbox is always local (not remote)
        super().__init__(
            remote=False,
            name=name,
        )

        self._project_root = (project_root or Path.cwd()).resolve()
        self._base_branch = base_branch
        self._auto_merge = auto_merge
        self._auto_cleanup = auto_cleanup
        self._worktrees_parent = worktrees_parent
        self._config = config or SandboxConfig()

        # Session management
        self._session_id: Optional[str] = None
        self._worktree_info: Optional[WorktreeInfo] = None
        self._manager: Optional[WorktreeIsolationManager] = None

        # Execution state
        self._execution_globals: Dict[str, Any] = {}
        self._compilation_cache: Dict[str, Any] = {}
        self._artifacts_dir: Optional[Path] = None

        # Original working directory (for restoration)
        self._original_cwd: Optional[Path] = None

        logger.info(f"WorktreeSandbox initialized: {name}")

    @property
    def name(self) -> str:
        """Get the sandbox name."""
        return self._name

    @property
    def session_id(self) -> Optional[str]:
        """Get the session ID."""
        return self._session_id

    @property
    def worktree_path(self) -> Optional[Path]:
        """Get the worktree path."""
        return self._worktree_info.worktree_path if self._worktree_info else None

    @property
    def base_branch(self) -> Optional[str]:
        """Get the base branch."""
        return self._base_branch

    @property
    def is_active(self) -> bool:
        """Check if the sandbox is active."""
        return self._worktree_info is not None and self._worktree_info.status in (
            WorktreeStatus.CREATED,
            WorktreeStatus.ACTIVE,
            WorktreeStatus.MODIFIED,
        )

    async def get_default_image(self) -> str:
        """
        Get the default Docker image for worktree sandbox (not used).
        """
        return "local-worktree"

    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
    ) -> None:
        """
        Start the worktree sandbox (no-op for worktree isolation).
        """
        await self._enter()

    async def stop(self) -> None:
        """
        Stop the worktree sandbox.
        """
        await self._exit()

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        name: Optional[str] = None,
        project_root: Optional[Path] = None,
        base_branch: Optional[str] = None,
        auto_merge: bool = False,
        auto_cleanup: bool = True,
        worktrees_parent: Optional[Path] = None,
        config: Optional[SandboxConfig] = None,
    ) -> AsyncIterator["WorktreeSandbox"]:
        """
        Create and enter a worktree sandbox context.

        Args:
            name: Sandbox name (auto-generated if not provided)
            project_root: Git repository root
            base_branch: Base branch for worktree
            auto_merge: Auto-merge on exit
            auto_cleanup: Auto-cleanup on exit
            worktrees_parent: Parent for worktrees
            config: Sandbox configuration

        Yields:
            The active WorktreeSandbox instance
        """
        sandbox = cls(
            name=name or f"worktree-{uuid.uuid4().hex[:12]}",
            project_root=project_root,
            base_branch=base_branch,
            auto_merge=auto_merge,
            auto_cleanup=auto_cleanup,
            worktrees_parent=worktrees_parent,
            config=config,
        )

        try:
            await sandbox._enter()
            yield sandbox
        finally:
            await sandbox._exit()

    async def _enter(self) -> None:
        """Enter the sandbox context."""
        # Create worktree manager
        self._manager = WorktreeIsolationManager(
            project_root=self._project_root,
            worktrees_parent=self._worktrees_parent,
        )

        # Save original directory
        self._original_cwd = Path.cwd()

        # Create worktree session
        self._worktree_info = await self._manager.create_session(
            session_id=self._name,
            base_branch=self._base_branch,
        )

        self._session_id = self._worktree_info.session_id

        # Change to worktree directory
        os.chdir(self._worktree_info.worktree_path)

        # Create artifacts directory
        self._artifacts_dir = self._worktree_info.worktree_path / ".sandbox_artifacts"
        self._artifacts_dir.mkdir(exist_ok=True)

        # Set up Python environment in worktree
        self._setup_environment()

        logger.info(
            f"Entered worktree sandbox: {self._name} at {self._worktree_info.worktree_path}"
        )

    async def _exit(self) -> None:
        """Exit the sandbox context."""
        if not self._worktree_info:
            return

        try:
            # Auto-merge if enabled
            if self._auto_merge:
                try:
                    await self.merge_changes()
                except MergeConflictError as e:
                    logger.warning(f"Auto-merge failed: {e}")

            # Cleanup if enabled
            if self._auto_cleanup:
                await self._cleanup()

        finally:
            # Restore original directory
            if self._original_cwd:
                os.chdir(self._original_cwd)

            logger.info(f"Exited worktree sandbox: {self._name}")

    def _setup_environment(self) -> None:
        """Set up Python environment in the worktree."""
        # Add worktree to sys.path
        worktree_str = str(self._worktree_info.worktree_path)
        if worktree_str not in sys.path:
            sys.path.insert(0, worktree_str)

        # Add parent directory to sys.path for package imports
        parent_str = str(self._worktree_info.worktree_path.parent)
        if parent_str not in sys.path:
            sys.path.insert(0, parent_str)

    async def run(self, code: str, **kwargs: Any) -> Execution:
        """
        Execute Python code in the worktree sandbox.

        Args:
            code: Python code to execute
            **kwargs: Additional execution options

        Returns:
            Execution result with artifacts captured
        """
        if not self.is_active:
            raise RuntimeError("Sandbox is not active. Use async with to enter.")

        try:
            # Capture output
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout = io.StringIO()
            stderr = io.StringIO()

            # Track artifacts before execution
            artifacts_before = self._get_artifacts() if self._artifacts_dir else set()

            # Execute code
            exception = None

            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    exec(compile(code, "<worktree_sandbox>", "exec"), self._execution_globals)
                except Exception as e:
                    exception = e

            # Track artifacts after execution
            artifacts_after = self._get_artifacts() if self._artifacts_dir else set()
            new_artifacts = artifacts_after - artifacts_before

            # Update worktree status
            if self._manager:
                self._worktree_info = await self._manager.get_session(self._session_id)

            return Execution(
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue(),
                exception=exception,
                artifacts=list(new_artifacts),
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return Execution(
                stdout="",
                stderr=str(e),
                exception=e,
                artifacts=[],
            )

    async def command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Command:
        """
        Execute a shell command in the worktree sandbox.

        Args:
            command: Command to execute
            args: Command arguments
            cwd: Working directory (defaults to worktree root)
            env: Environment variables
            timeout: Timeout in seconds

        Returns:
            Command execution result
        """
        if not self.is_active:
            raise RuntimeError("Sandbox is not active. Use async with to enter.")

        import subprocess

        cwd = cwd or self._worktree_info.worktree_path
        full_cmd = [command] + (args or [])

        try:
            result = subprocess.run(
                full_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            return Command(
                command=command,
                args=args or [],
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                success=result.returncode == 0,
            )

        except subprocess.TimeoutExpired:
            return Command(
                command=command,
                args=args or [],
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                success=False,
            )
        except Exception as e:
            return Command(
                command=command,
                args=args or [],
                stdout="",
                stderr=str(e),
                exit_code=-1,
                success=False,
            )

    async def get_changes(self) -> Dict[str, Any]:
        """
        Get changes made in the worktree.

        Returns:
            Dictionary with change information
        """
        if not self._manager or not self._session_id:
            return {}

        return await self._manager.get_changes(self._session_id)

    async def commit_changes(self, message: Optional[str] = None) -> str:
        """
        Commit changes in the worktree.

        Args:
            message: Commit message

        Returns:
            Commit hash
        """
        if not self._manager or not self._session_id:
            raise RuntimeError("Sandbox is not active")

        return await self._manager.commit_session(self._session_id, message)

    async def merge_changes(
        self,
        merge_message: Optional[str] = None,
        strategy: str = "merge",
    ) -> Dict[str, Any]:
        """
        Merge worktree changes back to the base branch.

        Args:
            merge_message: Optional merge commit message
            strategy: Merge strategy ("merge", "squash", "rebase")

        Returns:
            Merge result dictionary
        """
        if not self._manager or not self._session_id:
            raise RuntimeError("Sandbox is not active")

        return await self._manager.merge_session(self._session_id, merge_message, strategy)

    async def cleanup(self) -> None:
        """
        Clean up the worktree sandbox.

        This removes the worktree but preserves the session info for inspection.
        Use close() to fully remove the session.
        """
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Internal cleanup method."""
        if self._manager and self._session_id:
            await self._manager.close_session(
                self._session_id,
                keep_worktree=False,
            )
            self._worktree_info = None

    async def close(self) -> None:
        """Close the sandbox and clean up all resources."""
        await self._cleanup()
        if self._manager:
            await self._manager.cleanup_all()
            self._manager = None

    def _get_artifacts(self) -> Set[str]:
        """Get current artifacts from the artifacts directory."""
        if not self._artifacts_dir or not self._artifacts_dir.exists():
            return set()

        artifacts = set()
        for path in self._artifacts_dir.rglob("*"):
            if path.is_file():
                artifacts.add(str(path.relative_to(self._artifacts_dir)))
        return artifacts

    async def metrics(self) -> Metrics:
        """
        Get sandbox metrics.

        Returns:
            Metrics information
        """
        changes = await self.get_changes() if self._manager else {}

        return Metrics(
            cpu_usage=0.0,  # Not tracked for worktree isolation
            memory_usage=0,  # Not tracked for worktree isolation
            execution_time=0.0,  # Not tracked
            network_usage=0,  # Not tracked
            disk_usage=sum(
                f.stat().st_size
                for f in self._artifacts_dir.rglob("*")
                if f.is_file()
            ) if self._artifacts_dir else 0,
            extra={
                "session_id": self._session_id,
                "worktree_path": str(self._worktree_info.worktree_path) if self._worktree_info else None,
                "base_branch": self._base_branch,
                "changed_files": len(changes.get("changed_files", [])),
                "status": self._worktree_info.status.value if self._worktree_info else None,
            },
        )
