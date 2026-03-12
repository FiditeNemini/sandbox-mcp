"""
Git worktree management for sandbox isolation.

This module provides filesystem isolation using git worktrees, allowing each
sandbox session to have its own isolated working directory with optional
merge capabilities back to the main branch.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class WorktreeManager:
    """
    Manage git worktrees for sandbox isolation.

    Each session can have its own worktree, providing:
    - Complete filesystem isolation
    - Independent git state
    - Optional merge back to main
    """

    def __init__(self, repo_root: Path):
        """
        Initialize the worktree manager.

        Args:
            repo_root: Path to the git repository root
        """
        self.repo_root = repo_root
        self._worktrees_dir = repo_root / ".sandbox-worktrees"
        self._worktrees_dir.mkdir(exist_ok=True)

    def _is_git_repo(self) -> bool:
        """Check if the current path is a git repository."""
        return (self.repo_root / ".git").exists()

    def _get_current_branch(self) -> Optional[str]:
        """
        Get the current branch name.

        Returns:
            Current branch name or None if not on a branch
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
            return branch if branch != "HEAD" else None
        except subprocess.CalledProcessError:
            return None

    def create_worktree(
        self,
        session_id: str,
        base_branch: Optional[str] = None,
    ) -> Tuple[Path, str]:
        """
        Create a new worktree for a session.

        Args:
            session_id: Session identifier
            base_branch: Base branch to create from (defaults to current branch)

        Returns:
            Tuple of (worktree_path, branch_name)

        Raises:
            RuntimeError: If worktree creation fails
            ValueError: If not in a git repository
        """
        if not self._is_git_repo():
            raise ValueError("Worktree isolation requires a git repository")

        # Use provided branch or current branch
        if base_branch is None:
            base_branch = self._get_current_branch()
            if base_branch is None:
                # Not on a branch, use HEAD detached
                base_branch = "HEAD"

        # Use HEAD if base_branch is empty (detached state)
        if not base_branch:
            base_branch = "HEAD"

        branch_name = f"sandbox/{session_id}"
        worktree_path = self._worktrees_dir / session_id

        # Check if worktree already exists
        if worktree_path.exists() and (worktree_path / ".git").exists():
            logger.warning(f"Worktree already exists: {worktree_path}")
            # Verify the branch matches
            try:
                result = subprocess.run(
                    ["git", "worktree", "list", "--porcelain"],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Check if this worktree is registered
                for line in result.stdout.splitlines():
                    if line.startswith("worktree ") and str(worktree_path) in line:
                        return worktree_path, branch_name
            except subprocess.CalledProcessError:
                pass

        # Create new worktree with a new branch
        cmd = [
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            base_branch,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Created worktree: {worktree_path} from {base_branch}")
            return worktree_path, branch_name
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create worktree: {e.stderr}")
            raise RuntimeError(f"Failed to create worktree: {e.stderr}") from e

    def get_worktree_status(self, session_id: str) -> dict:
        """
        Get the git status of a worktree.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with status information
        """
        branch_name = f"sandbox/{session_id}"
        worktree_path = self._worktrees_dir / session_id

        if not worktree_path.exists():
            return {"exists": False}

        try:
            # Get status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )

            changes = result.stdout.strip().splitlines() if result.stdout.strip() else []

            return {
                "exists": True,
                "path": str(worktree_path),
                "branch": branch_result.stdout.strip(),
                "has_changes": len(changes) > 0,
                "changed_files": len(changes),
                "files": changes,
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get worktree status: {e.stderr}")
            return {"exists": True, "error": str(e)}

    def commit_worktree_changes(
        self,
        session_id: str,
        message: str = "Sandbox session changes",
    ) -> bool:
        """
        Commit changes in a worktree.

        Args:
            session_id: Session identifier
            message: Commit message

        Returns:
            True if commit succeeded
        """
        worktree_path = self._worktrees_dir / session_id

        if not worktree_path.exists():
            logger.warning(f"Worktree does not exist: {worktree_path}")
            return False

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
            )

            # Check if there's anything to commit
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=worktree_path,
                capture_output=True,
            )

            # Return code 1 means there are changes
            if result.returncode == 0:
                logger.info(f"No changes to commit in worktree: {session_id}")
                return True

            # Commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=worktree_path,
                check=True,
                capture_output=True,
            )

            logger.info(f"Committed changes in worktree: {session_id}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit worktree changes: {e.stderr}")
            return False

    def merge_worktree(
        self,
        session_id: str,
        target_branch: str = "main",
        delete_after: bool = True,
        commit_message: Optional[str] = None,
    ) -> bool:
        """
        Merge worktree changes back to target branch.

        Args:
            session_id: Session identifier
            target_branch: Branch to merge into
            delete_after: Delete worktree after merge
            commit_message: Optional custom commit message

        Returns:
            True if merge succeeded
        """
        branch_name = f"sandbox/{session_id}"

        try:
            # Checkout target branch in main repo
            subprocess.run(
                ["git", "checkout", target_branch],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
            )

            # Pull latest changes first
            try:
                subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                logger.warning(f"Could not pull latest changes for {target_branch}")

            # Merge session branch
            msg = commit_message or f"Merge sandbox session: {session_id}"
            result = subprocess.run(
                ["git", "merge", branch_name, "--no-ff", "-m", msg],
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                # Check if it's a conflict
                if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                    logger.error(f"Merge conflicts detected when merging {branch_name}")
                    # Abort the merge
                    subprocess.run(
                        ["git", "merge", "--abort"],
                        cwd=self.repo_root,
                        capture_output=True,
                    )
                    return False
                logger.error(f"Merge failed: {result.stderr}")
                return False

            logger.info(f"Merged {branch_name} into {target_branch}")

            if delete_after:
                self.delete_worktree(session_id)

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Merge failed: {e.stderr}")
            return False

    def delete_worktree(self, session_id: str) -> bool:
        """
        Delete a worktree.

        Args:
            session_id: Session identifier

        Returns:
            True if deletion succeeded
        """
        branch_name = f"sandbox/{session_id}"
        worktree_path = self._worktrees_dir / session_id

        try:
            # Prune worktrees first to remove stale references
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_root,
                capture_output=True,
            )

            # Remove worktree using git worktree remove
            if worktree_path.exists():
                result = subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path), "--force"],
                    cwd=self.repo_root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                # Force remove directory if git command fails
                if result.returncode != 0:
                    import shutil

                    shutil.rmtree(worktree_path, ignore_errors=True)

            # Delete the branch
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=self.repo_root,
                check=False,
                capture_output=True,
            )

            logger.info(f"Deleted worktree: {worktree_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete worktree: {e}")
            return False

    def list_worktrees(self) -> List[Tuple[str, Path, str]]:
        """
        List all sandbox worktrees.

        Returns:
            List of tuples (session_id, path, branch)
        """
        worktrees = []

        if not self._worktrees_dir.exists():
            return worktrees

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            current_worktree = None
            current_branch = None

            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    current_worktree = Path(line.split(" ", 1)[1])
                elif line.startswith("branch "):
                    current_branch = line.split(" ", 1)[1]
                    # Extract branch name from refs/heads/
                    if current_branch.startswith("refs/heads/"):
                        current_branch = current_branch[11:]
                elif line == "" and current_worktree is not None:
                    # End of worktree entry
                    # Only include sandbox worktrees
                    if str(self._worktrees_dir) in str(current_worktree):
                        session_id = current_worktree.name
                        worktrees.append((session_id, current_worktree, current_branch or "unknown"))
                    current_worktree = None
                    current_branch = None

        except subprocess.CalledProcessError:
            # Fallback to directory scanning
            for item in self._worktrees_dir.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    session_id = item.name
                    worktrees.append((session_id, item, f"sandbox/{session_id}"))

        return worktrees

    def cleanup_all(self) -> int:
        """
        Remove all sandbox worktrees.

        Returns:
            Number of worktrees removed
        """
        count = 0
        for session_id, _, _ in self.list_worktrees():
            if self.delete_worktree(session_id):
                count += 1
        return count

    def get_worktree_path(self, session_id: str) -> Optional[Path]:
        """
        Get the path to a worktree for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to worktree or None if it doesn't exist
        """
        worktree_path = self._worktrees_dir / session_id
        return worktree_path if worktree_path.exists() and (worktree_path / ".git").exists() else None


def find_git_repo(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find the git repository root by searching upwards from a path.

    Args:
        start_path: Path to start searching from (defaults to current directory)

    Returns:
        Path to git repository root or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent

    return None
