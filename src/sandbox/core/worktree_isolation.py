"""
Git worktree isolation for complete filesystem separation.

This module provides worktree-style isolation by creating git worktrees
for each session, enabling complete filesystem isolation while maintaining
the ability to merge changes back to the main branch.

Security:
    Worktree paths are validated to prevent path traversal.
    All git operations are executed with proper error handling.

Limitations:
    Requires the project to be a git repository.
    Merge conflicts must be resolved manually.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .path_validation import PathValidator, is_safe_path


logger = logging.getLogger(__name__)


class WorktreeStatus(Enum):
    """Status of a worktree isolation session."""
    CREATED = "created"
    ACTIVE = "active"
    MODIFIED = "modified"
    MERGED = "merged"
    CONFLICT = "conflict"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class WorktreeInfo:
    """Information about a worktree session."""
    session_id: str
    worktree_path: Path
    base_branch: str
    base_commit: str
    worktree_branch: str
    status: WorktreeStatus
    created_at: datetime
    modified_at: datetime
    changed_files: Set[str] = field(default_factory=set)
    merge_message: Optional[str] = None


class GitError(Exception):
    """Base exception for git-related errors."""
    pass


class GitNotFoundError(GitError):
    """Git is not available on the system."""
    pass


class NotARepositoryError(GitError):
    """The project is not a git repository."""
    pass


class WorktreeCreationError(GitError):
    """Failed to create a worktree."""
    pass


class MergeConflictError(GitError):
    """Merge resulted in conflicts."""
    pass


class WorktreeIsolationManager:
    """
    Manages git worktree isolation for sandbox sessions.

    Each session gets its own worktree with complete filesystem isolation.
    Changes can be merged back to the base branch on demand.

    Usage:
        manager = WorktreeIsolationManager(project_root=Path("/project"))

        # Create a new isolated session
        worktree_info = await manager.create_session(
            session_id="session-123",
            base_branch="main"
        )

        # Work in the isolated environment
        worktree_path = worktree_info.worktree_path

        # Check for changes
        changes = await manager.get_changes(worktree_info.session_id)

        # Merge back to base branch
        await manager.merge_session(worktree_info.session_id)

        # Clean up
        await manager.close_session(worktree_info.session_id)
    """

    def __init__(
        self,
        project_root: Path,
        worktrees_parent: Optional[Path] = None,
        auto_cleanup: bool = True,
    ):
        """
        Initialize the worktree isolation manager.

        Args:
            project_root: The git repository to create worktrees from
            worktrees_parent: Parent directory for worktrees (default: project_root/.worktrees)
            auto_cleanup: Automatically clean up worktrees on close

        Raises:
            GitNotFoundError: If git is not available
            NotARepositoryError: If project_root is not a git repository
        """
        self._project_root = Path(project_root).resolve()
        self._worktrees_parent = worktrees_parent or (self._project_root / ".worktrees")
        self._worktrees_parent = Path(self._worktrees_parent).resolve()
        self._auto_cleanup = auto_cleanup

        self._sessions: Dict[str, WorktreeInfo] = {}
        self._lock = threading.RLock()

        # Verify git is available
        self._check_git_available()

        # Verify project is a git repository
        self._check_git_repository()

        # Create worktrees parent directory
        self._worktrees_parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"WorktreeIsolationManager initialized for {self._project_root}")

    def _check_git_available(self) -> None:
        """Check if git is available on the system."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise GitNotFoundError("Git command failed")
            logger.debug(f"Git version: {result.stdout.strip()}")
        except FileNotFoundError:
            raise GitNotFoundError("Git is not installed or not in PATH")
        except subprocess.TimeoutExpired:
            raise GitNotFoundError("Git command timed out")

    def _check_git_repository(self) -> None:
        """Check if project_root is a git repository."""
        git_dir = self._project_root / ".git"
        if not git_dir.exists():
            raise NotARepositoryError(
                f"{self._project_root} is not a git repository"
            )

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run a git command with proper error handling.

        Args:
            args: Git command arguments
            cwd: Working directory (default: project_root)
            check: Raise exception on non-zero exit
            timeout: Command timeout in seconds

        Returns:
            Completed process result

        Raises:
            GitError: If the command fails
        """
        cwd = cwd or self._project_root
        cmd = ["git"] + args

        logger.debug(f"Running git command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if check and result.returncode != 0:
                raise GitError(
                    f"Git command failed: {result.stderr or result.stdout}"
                )

            return result

        except subprocess.TimeoutExpired:
            raise GitError(f"Git command timed out: {' '.join(args)}")
        except FileNotFoundError:
            raise GitNotFoundError("Git is not available")

    def _get_current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run_git(
            ["branch", "--show-current"],
            check=True,
        )
        return result.stdout.strip()

    def _get_current_commit(self, branch: Optional[str] = None) -> str:
        """Get the current commit hash."""
        args = ["rev-parse", "HEAD"]
        if branch:
            args = ["rev-parse", branch]
        result = self._run_git(args, check=True)
        return result.stdout.strip()

    def _get_changed_files(self, worktree_path: Path, base_commit: str) -> Set[str]:
        """Get list of files changed in the worktree."""
        try:
            # Get diff against base commit
            result = self._run_git(
                ["diff", "--name-only", base_commit],
                cwd=worktree_path,
                check=False,
            )

            if result.returncode != 0:
                return set()

            changed = set()
            for line in result.stdout.splitlines():
                if line.strip():
                    # Validate path is within worktree
                    file_path = (worktree_path / line.strip()).resolve()
                    if file_path.is_relative_to(worktree_path.resolve()):
                        changed.add(line.strip())

            return changed

        except GitError:
            return set()

    async def create_session(
        self,
        session_id: Optional[str] = None,
        base_branch: Optional[str] = None,
    ) -> WorktreeInfo:
        """
        Create a new isolated worktree session.

        Args:
            session_id: Unique session identifier (auto-generated if not provided)
            base_branch: Base branch to create worktree from (default: current branch)

        Returns:
            WorktreeInfo with session details

        Raises:
            WorktreeCreationError: If worktree creation fails
        """
        with self._lock:
            session_id = session_id or f"session-{uuid.uuid4().hex[:12]}"
            base_branch = base_branch or self._get_current_branch()

            # Validate session_id to prevent path traversal
            safe_session_id = PathValidator.sanitize_path_component(session_id)

            # Create worktree branch name
            worktree_branch = f"worktree/{safe_session_id}"

            # Get base commit
            base_commit = self._get_current_commit(base_branch)

            # Create worktree path
            worktree_path = self._worktrees_parent / safe_session_id

            # Validate worktree path
            if not is_safe_path(worktree_path, require_exists=False):
                raise WorktreeCreationError(
                    f"Invalid worktree path: {worktree_path}"
                )

            try:
                # Create the worktree
                result = self._run_git(
                    [
                        "worktree",
                        "add",
                        "-b", worktree_branch,
                        str(worktree_path),
                        base_branch,
                    ],
                    check=True,
                )

                logger.info(f"Created worktree: {worktree_path}")

                # Create session info
                info = WorktreeInfo(
                    session_id=session_id,
                    worktree_path=worktree_path,
                    base_branch=base_branch,
                    base_commit=base_commit,
                    worktree_branch=worktree_branch,
                    status=WorktreeStatus.CREATED,
                    created_at=datetime.now(),
                    modified_at=datetime.now(),
                )

                self._sessions[session_id] = info
                return info

            except GitError as e:
                raise WorktreeCreationError(f"Failed to create worktree: {e}")

    async def get_session(self, session_id: str) -> Optional[WorktreeInfo]:
        """Get session info by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Update changed files
                session.changed_files = self._get_changed_files(
                    session.worktree_path,
                    session.base_commit,
                )
                # Update status based on changes
                if session.changed_files and session.status == WorktreeStatus.ACTIVE:
                    session.status = WorktreeStatus.MODIFIED
            return session

    async def list_sessions(self) -> List[WorktreeInfo]:
        """List all active sessions."""
        with self._lock:
            return list(self._sessions.values())

    async def get_changes(self, session_id: str) -> Dict[str, Any]:
        """
        Get changes made in a worktree session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary with changes info:
            {
                "changed_files": ["path/to/file1", "path/to/file2"],
                "added_files": ["path/to/new"],
                "modified_files": ["path/to/modified"],
                "deleted_files": ["path/to/deleted"],
                "diff": "unified diff output",
            }
        """
        info = await self.get_session(session_id)
        if not info:
            return {}

        try:
            # Get detailed diff
            diff_result = self._run_git(
                ["diff", info.base_commit],
                cwd=info.worktree_path,
                check=False,
            )

            # Get file status
            status_result = self._run_git(
                ["status", "--porcelain"],
                cwd=info.worktree_path,
                check=False,
            )

            added = set()
            modified = set()
            deleted = set()

            for line in status_result.stdout.splitlines():
                if not line.strip():
                    continue
                status_code, path = line[:2], line[3:].strip()
                if "A" in status_code or "??" in status_code:
                    added.add(path)
                elif "M" in status_code:
                    modified.add(path)
                elif "D" in status_code:
                    deleted.add(path)

            return {
                "session_id": session_id,
                "changed_files": list(info.changed_files),
                "added_files": list(added),
                "modified_files": list(modified),
                "deleted_files": list(deleted),
                "diff": diff_result.stdout,
                "base_commit": info.base_commit,
            }

        except GitError as e:
            logger.error(f"Failed to get changes for {session_id}: {e}")
            return {}

    async def commit_session(
        self,
        session_id: str,
        message: Optional[str] = None,
    ) -> str:
        """
        Commit changes in a worktree session.

        Args:
            session_id: The session identifier
            message: Commit message (auto-generated if not provided)

        Returns:
            The commit hash

        Raises:
            GitError: If commit fails
        """
        info = await self.get_session(session_id)
        if not info:
            raise GitError(f"Session not found: {session_id}")

        # Generate default commit message
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Sandbox session {session_id} changes ({timestamp})"

        try:
            # Stage all changes
            self._run_git(
                ["add", "-A"],
                cwd=info.worktree_path,
                check=True,
            )

            # Commit
            result = self._run_git(
                ["commit", "-m", message],
                cwd=info.worktree_path,
                check=True,
            )

            # Get new commit hash
            commit_result = self._run_git(
                ["rev-parse", "HEAD"],
                cwd=info.worktree_path,
                check=True,
            )

            info.status = WorktreeStatus.ACTIVE
            logger.info(f"Committed changes in {session_id}")

            return commit_result.stdout.strip()

        except GitError as e:
            info.status = WorktreeStatus.ERROR
            raise GitError(f"Failed to commit changes: {e}")

    async def merge_session(
        self,
        session_id: str,
        merge_message: Optional[str] = None,
        strategy: str = "merge",
    ) -> Dict[str, Any]:
        """
        Merge worktree changes back to the base branch.

        Args:
            session_id: The session identifier
            merge_message: Optional merge commit message
            strategy: Merge strategy ("merge", "squash", "rebase")

        Returns:
            Dictionary with merge result:
            {
                "success": bool,
                "conflicts": ["path/to/conflict1"],
                "merge_commit": str or None,
            }

        Raises:
            MergeConflictError: If merge results in conflicts
        """
        info = await self.get_session(session_id)
        if not info:
            raise GitError(f"Session not found: {session_id}")

        try:
            # Ensure changes are committed
            if info.changed_files:
                await self.commit_session(session_id)

            if strategy == "merge":
                return await self._merge_merge(info, merge_message)
            elif strategy == "squash":
                return await self._merge_squash(info, merge_message)
            elif strategy == "rebase":
                return await self._merge_rebase(info)
            else:
                raise GitError(f"Unknown merge strategy: {strategy}")

        except GitError as e:
            info.status = WorktreeStatus.ERROR
            raise

    async def _merge_merge(
        self,
        info: WorktreeInfo,
        merge_message: Optional[str],
    ) -> Dict[str, Any]:
        """Merge using standard git merge."""
        try:
            # Merge worktree branch into base branch
            result = self._run_git(
                ["merge", "--no-ff", info.worktree_branch, "-m", merge_message or f"Merge {info.worktree_branch}"],
                check=False,
            )

            if result.returncode != 0:
                # Check for conflicts
                conflict_result = self._run_git(
                    ["diff", "--name-only", "--diff-filter=U"],
                    check=False,
                )

                conflicts = [
                    line.strip()
                    for line in conflict_result.stdout.splitlines()
                    if line.strip()
                ]

                info.status = WorktreeStatus.CONFLICT

                raise MergeConflictError(
                    f"Merge conflicts in {len(conflicts)} files: {conflicts}"
                )

            info.status = WorktreeStatus.MERGED
            logger.info(f"Merged {session_id} into {info.base_branch}")

            return {
                "success": True,
                "conflicts": [],
                "merge_commit": self._get_current_commit(),
            }

        except MergeConflictError:
            raise
        except GitError as e:
            info.status = WorktreeStatus.ERROR
            raise

    async def _merge_squash(
        self,
        info: WorktreeInfo,
        commit_message: Optional[str],
    ) -> Dict[str, Any]:
        """Squash merge worktree changes."""
        try:
            # Squash merge
            self._run_git(
                ["merge", "--squash", info.worktree_branch],
                check=True,
            )

            # Commit the squash
            message = commit_message or f"Squashed changes from {info.worktree_branch}"
            self._run_git(
                ["commit", "-m", message],
                check=True,
            )

            info.status = WorktreeStatus.MERGED
            logger.info(f"Squash merged {info.session_id}")

            return {
                "success": True,
                "conflicts": [],
                "merge_commit": self._get_current_commit(),
            }

        except GitError as e:
            info.status = WorktreeStatus.ERROR
            raise GitError(f"Squash merge failed: {e}")

    async def _merge_rebase(self, info: WorktreeInfo) -> Dict[str, Any]:
        """Rebase worktree branch onto base branch."""
        try:
            # Checkout base branch
            self._run_git(["checkout", info.base_branch], check=True)

            # Rebase worktree branch
            result = self._run_git(
                ["rebase", info.worktree_branch],
                check=False,
            )

            if result.returncode != 0:
                # Abort rebase on conflict
                self._run_git(["rebase", "--abort"], check=False)
                info.status = WorktreeStatus.CONFLICT
                raise MergeConflictError("Rebase resulted in conflicts")

            info.status = WorktreeStatus.MERGED
            logger.info(f"Rebased {info.session_id}")

            return {
                "success": True,
                "conflicts": [],
                "merge_commit": self._get_current_commit(),
            }

        except MergeConflictError:
            raise
        except GitError as e:
            info.status = WorktreeStatus.ERROR
            raise

    async def close_session(
        self,
        session_id: str,
        keep_worktree: bool = False,
    ) -> bool:
        """
        Close a worktree session and optionally clean up.

        Args:
            session_id: The session identifier
            keep_worktree: If True, keep the worktree directory

        Returns:
            True if session was closed successfully
        """
        with self._lock:
            info = self._sessions.get(session_id)
            if not info:
                return False

            try:
                # Remove the git worktree
                if not keep_worktree:
                    self._run_git(
                        ["worktree", "remove", str(info.worktree_path)],
                        check=False,
                    )
                    logger.info(f"Removed worktree: {info.worktree_path}")

                # Remove the worktree branch
                self._run_git(
                    ["branch", "-D", info.worktree_branch],
                    check=False,
                )

                info.status = WorktreeStatus.CLOSED
                del self._sessions[session_id]

                logger.info(f"Closed session: {session_id}")
                return True

            except GitError as e:
                logger.error(f"Failed to close session {session_id}: {e}")
                info.status = WorktreeStatus.ERROR
                return False

    async def cleanup_all(self) -> int:
        """
        Clean up all active sessions.

        Returns:
            Number of sessions cleaned up
        """
        sessions = list(self._sessions.keys())
        cleaned = 0
        for session_id in sessions:
            if await self.close_session(session_id):
                cleaned += 1
        return cleaned

    @contextmanager
    def isolated_context(
        self,
        session_id: Optional[str] = None,
        base_branch: Optional[str] = None,
        auto_merge: bool = False,
        auto_cleanup: bool = True,
    ):
        """
        Context manager for temporary worktree isolation.

        Args:
            session_id: Optional session identifier
            base_branch: Base branch to create worktree from
            auto_merge: Auto-merge changes on exit
            auto_cleanup: Auto-cleanup worktree on exit

        Yields:
            WorktreeInfo for the session
        """
        info = None
        try:
            # Create the session
            loop = asyncio.get_event_loop()
            info = loop.run_until_complete(
                self.create_session(session_id, base_branch)
            )

            # Change to worktree directory
            original_cwd = Path.cwd()
            os.chdir(info.worktree_path)

            yield info

            # Auto-merge if requested
            if auto_merge:
                loop.run_until_complete(
                    self.merge_session(info.session_id)
                )

        finally:
            # Restore original directory
            if info:
                os.chdir(original_cwd)

                # Cleanup if requested
                if auto_cleanup:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(
                        self.close_session(info.session_id, keep_worktree=False)
                    )


# Singleton instance
_worktree_manager: Optional[WorktreeIsolationManager] = None
_manager_lock = threading.Lock()


def get_worktree_manager(
    project_root: Optional[Path] = None,
) -> WorktreeIsolationManager:
    """
    Get or create the global worktree isolation manager.

    Args:
        project_root: Project root path (uses current directory if not provided)

    Returns:
        The WorktreeIsolationManager instance
    """
    global _worktree_manager

    with _manager_lock:
        if _worktree_manager is None:
            if project_root is None:
                project_root = Path.cwd()
            _worktree_manager = WorktreeIsolationManager(project_root=project_root)

        return _worktree_manager
