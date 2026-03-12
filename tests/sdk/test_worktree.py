"""
Tests for git worktree isolation in the Sandbox SDK.

These tests verify that worktree-based isolation works correctly
for parallel development workflows.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox.sdk.config import SandboxConfig, IsolationLevel, SandboxOptions
from sandbox.sdk.local_sandbox import LocalSandbox
from sandbox.core.worktree_manager import WorktreeManager, find_git_repo


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    (repo / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


@pytest.fixture
def worktree_manager(git_repo):
    """Create a WorktreeManager instance for testing."""
    return WorktreeManager(git_repo)


class TestWorktreeManager:
    """Tests for the WorktreeManager class."""

    def test_init_creates_worktrees_directory(self, git_repo):
        """Test that WorktreeManager creates the .sandbox-worktrees directory."""
        manager = WorktreeManager(git_repo)
        worktrees_dir = git_repo / ".sandbox-worktrees"

        assert worktrees_dir.exists()
        assert worktrees_dir.is_dir()

    def test_is_git_repo(self, git_repo):
        """Test _is_git_repo correctly identifies a git repository."""
        manager = WorktreeManager(git_repo)

        assert manager._is_git_repo()

    def test_is_git_repo_fails_for_non_repo(self, tmp_path):
        """Test _is_git_repo returns False for non-git directory."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()

        manager = WorktreeManager(non_repo)

        assert not manager._is_git_repo()

    def test_get_current_branch(self, git_repo):
        """Test getting the current branch name."""
        manager = WorktreeManager(git_repo)

        branch = manager._get_current_branch()

        assert branch is not None
        # Default branch is either main or master depending on git version
        assert branch in ("main", "master")

    def test_create_worktree(self, git_repo):
        """Test creating a worktree for a session."""
        manager = WorktreeManager(git_repo)

        worktree_path, branch_name = manager.create_worktree(
            session_id="test_session",
            base_branch=None,  # Use current branch
        )

        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()
        assert branch_name == "sandbox/test_session"

        # Verify the worktree has the same files
        assert (worktree_path / "README.md").exists()

    def test_create_worktree_with_custom_branch(self, git_repo):
        """Test creating a worktree from a specific base branch."""
        manager = WorktreeManager(git_repo)

        # Get current branch
        current_branch = manager._get_current_branch()

        worktree_path, branch_name = manager.create_worktree(
            session_id="test_session2",
            base_branch=current_branch,
        )

        assert worktree_path.exists()
        assert branch_name == "sandbox/test_session2"

    def test_create_worktree_fails_for_non_repo(self, tmp_path):
        """Test that create_worktree raises ValueError for non-git directory."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()

        manager = WorktreeManager(non_repo)

        with pytest.raises(ValueError, match="git repository"):
            manager.create_worktree("test_session")

    def test_get_worktree_status(self, git_repo):
        """Test getting worktree status."""
        manager = WorktreeManager(git_repo)

        # Create a worktree
        manager.create_worktree("test_session")

        # Add a file to the worktree
        worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
        (worktree_path / "new_file.txt").write_text("test content")

        # Get status
        status = manager.get_worktree_status("test_session")

        assert status["exists"] is True
        assert status["path"] == str(worktree_path)
        assert status["has_changes"] is True
        assert status["changed_files"] == 1

    def test_get_worktree_status_for_nonexistent(self, git_repo):
        """Test getting status for non-existent worktree."""
        manager = WorktreeManager(git_repo)

        status = manager.get_worktree_status("nonexistent")

        assert status["exists"] is False

    def test_commit_worktree_changes(self, git_repo):
        """Test committing changes in a worktree."""
        manager = WorktreeManager(git_repo)

        # Create a worktree and add a file
        manager.create_worktree("test_session")
        worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
        (worktree_path / "new_file.txt").write_text("test content")

        # Commit changes
        result = manager.commit_worktree_changes(
            "test_session",
            message="Test commit",
        )

        assert result is True

        # Verify file was committed
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == ""

    def test_list_worktrees(self, git_repo):
        """Test listing all worktrees."""
        manager = WorktreeManager(git_repo)

        # Create multiple worktrees
        manager.create_worktree("session1")
        manager.create_worktree("session2")

        worktrees = manager.list_worktrees()

        assert len(worktrees) == 2
        session_ids = [w[0] for w in worktrees]
        assert "session1" in session_ids
        assert "session2" in session_ids

    def test_delete_worktree(self, git_repo):
        """Test deleting a worktree."""
        manager = WorktreeManager(git_repo)

        # Create a worktree
        manager.create_worktree("test_session")
        worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
        assert worktree_path.exists()

        # Delete it
        result = manager.delete_worktree("test_session")

        assert result is True
        assert not worktree_path.exists()

    def test_cleanup_all(self, git_repo):
        """Test cleaning up all worktrees."""
        manager = WorktreeManager(git_repo)

        # Create multiple worktrees
        manager.create_worktree("session1")
        manager.create_worktree("session2")
        manager.create_worktree("session3")

        count = manager.cleanup_all()

        assert count == 3

        # Verify all worktrees are gone
        worktrees = manager.list_worktrees()
        assert len(worktrees) == 0

    def test_merge_worktree(self, git_repo):
        """Test merging a worktree back to main branch."""
        manager = WorktreeManager(git_repo)

        # Get current branch (main or master)
        current_branch = manager._get_current_branch()

        # Create a worktree and make changes
        manager.create_worktree("test_session")
        worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
        (worktree_path / "new_file.txt").write_text("test content")

        # Commit changes in worktree
        manager.commit_worktree_changes("test_session", "Add new file")

        # Merge back to main
        result = manager.merge_worktree(
            "test_session",
            target_branch=current_branch,
            delete_after=False,
        )

        assert result is True

        # Verify file exists in main repo
        assert (git_repo / "new_file.txt").exists()

    def test_get_worktree_path(self, git_repo):
        """Test getting the path to a worktree."""
        manager = WorktreeManager(git_repo)

        manager.create_worktree("test_session")
        path = manager.get_worktree_path("test_session")

        assert path == git_repo / ".sandbox-worktrees" / "test_session"

    def test_get_worktree_path_nonexistent(self, git_repo):
        """Test getting path for non-existent worktree."""
        manager = WorktreeManager(git_repo)

        path = manager.get_worktree_path("nonexistent")

        assert path is None


class TestFindGitRepo:
    """Tests for the find_git_repo utility function."""

    def test_find_git_repo_from_repo_root(self, git_repo):
        """Test finding git repo from the repo root."""
        result = find_git_repo(git_repo)

        assert result == git_repo

    def test_find_git_repo_from_subdirectory(self, git_repo):
        """Test finding git repo from a subdirectory."""
        subdir = git_repo / "subdir"
        subdir.mkdir()

        result = find_git_repo(subdir)

        assert result == git_repo

    def test_find_git_repo_from_non_repo(self, tmp_path):
        """Test finding git repo when not in one."""
        result = find_git_repo(tmp_path)

        assert result is None


class TestLocalSandboxWorktree:
    """Tests for LocalSandbox with worktree isolation."""

    @pytest.mark.asyncio
    async def test_worktree_isolation_enabled(self, git_repo):
        """Test that worktree isolation is enabled when configured."""
        config = SandboxOptions.builder().worktree().build()

        sandbox = LocalSandbox(config=config, name="test_session")

        assert sandbox._config.isolation_level == IsolationLevel.WORKTREE
        assert sandbox._config.auto_delete_worktree is True

    @pytest.mark.asyncio
    async def test_worktree_setup_fails_for_non_repo(self, tmp_path):
        """Test that worktree setup fails outside a git repository."""
        # Change to non-git directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            config = SandboxOptions.builder().worktree().build()
            sandbox = LocalSandbox(config=config, name="test_session")

            with pytest.raises(ValueError, match="git repository"):
                await sandbox.start()
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_worktree_setup_creates_worktree(self, git_repo):
        """Test that starting a sandbox with worktree creates a worktree."""
        # Change to git repo
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            config = SandboxOptions.builder().worktree().build()
            sandbox = LocalSandbox(config=config, name="test_session")

            await sandbox.start()

            # Verify worktree was created
            worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
            assert worktree_path.exists()

            await sandbox.stop()

        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_worktree_deleted_on_close(self, git_repo):
        """Test that worktree is deleted when auto_delete_worktree=True."""
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            config = SandboxOptions.builder().worktree(auto_delete=True).build()
            sandbox = LocalSandbox(config=config, name="test_session")

            await sandbox.start()

            worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
            assert worktree_path.exists()

            await sandbox.stop()

            # Worktree should be deleted
            assert not worktree_path.exists()

        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_worktree_preserved_on_close(self, git_repo):
        """Test that worktree is preserved when auto_delete_worktree=False."""
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            config = SandboxOptions.builder().worktree(auto_delete=False).build()
            sandbox = LocalSandbox(config=config, name="test_session")

            await sandbox.start()

            worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
            assert worktree_path.exists()

            await sandbox.stop()

            # Worktree should still exist
            assert worktree_path.exists()

            # Cleanup
            manager = WorktreeManager(git_repo)
            manager.delete_worktree("test_session")

        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_worktree_with_auto_merge(self, git_repo):
        """Test that worktree with auto_merge commits and merges changes."""
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            # Get current branch
            manager = WorktreeManager(git_repo)
            current_branch = manager._get_current_branch()

            config = SandboxOptions.builder().worktree(
                auto_merge=True,
                auto_delete=True,
            ).build()
            sandbox = LocalSandbox(config=config, name="test_session")

            await sandbox.start()

            # Create a file in the worktree
            worktree_path = git_repo / ".sandbox-worktrees" / "test_session"
            (worktree_path / "new_file.txt").write_text("test content")

            await sandbox.stop()

            # File should be merged into main repo
            assert (git_repo / "new_file.txt").exists()

        finally:
            os.chdir(original_cwd)


class TestSandboxConfigWorktree:
    """Tests for SandboxConfig worktree settings."""

    def test_default_worktree_settings(self):
        """Test default worktree configuration values."""
        config = SandboxConfig()

        assert config.isolation_level == IsolationLevel.IN_PROCESS
        assert config.worktree_base_branch is None
        assert config.auto_merge_on_close is False
        assert config.auto_delete_worktree is True

    def test_worktree_builder_method(self):
        """Test the worktree() builder method."""
        config = (
            SandboxOptions.builder()
            .worktree(
                base_branch="develop",
                auto_merge=True,
                auto_delete=False,
                commit_message="Custom message",
            )
            .build()
        )

        assert config.isolation_level == IsolationLevel.WORKTREE
        assert config.worktree_base_branch == "develop"
        assert config.auto_merge_on_close is True
        assert config.auto_delete_worktree is False
        assert config.worktree_commit_message == "Custom message"

    def test_isolation_level_builder_method(self):
        """Test the isolation_level() builder method."""
        config = (
            SandboxOptions.builder()
            .isolation_level(IsolationLevel.WORKTREE)
            .build()
        )

        assert config.isolation_level == IsolationLevel.WORKTREE


@pytest.mark.integration
class TestWorktreeIntegration:
    """Integration tests for worktree functionality (requires git)."""

    def test_worktree_with_git_commands(self, git_repo):
        """Test that worktree works with actual git commands."""
        manager = WorktreeManager(git_repo)

        # Create worktree
        worktree_path, branch = manager.create_worktree("integration_test")

        # Verify git commands work in worktree
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        # Should succeed with no output (clean status)
        assert result.returncode == 0

        # Add a file
        (worktree_path / "test.txt").write_text("content")

        # Verify status shows the new file
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        assert "test.txt" in result.stdout
