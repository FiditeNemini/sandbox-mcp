"""
Tests for worktree isolation functionality.

These tests verify the git worktree-based isolation system.
"""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from sandbox.core.worktree_isolation import (
    WorktreeIsolationManager,
    WorktreeInfo,
    WorktreeStatus,
    get_worktree_manager,
    GitError,
    GitNotFoundError,
    NotARepositoryError,
    WorktreeCreationError,
    MergeConflictError,
)


class TestWorktreeIsolationManager(unittest.TestCase):
    """Test the WorktreeIsolationManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _init_git_repo(self):
        """Initialize a git repository in the temp directory."""
        import subprocess

        subprocess.run(["git", "init"], cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=self.temp_dir, check=True, capture_output=True)

        # Create initial commit
        test_file = self.project_root / "test.txt"
        test_file.write_text("Initial content")
        subprocess.run(["git", "add", "."], cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                      cwd=self.temp_dir, check=True, capture_output=True)

    def test_init_fails_without_git(self):
        """Test that initialization fails when git is not available."""
        with patch("sandbox.core.worktree_isolation.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            with self.assertRaises(GitNotFoundError):
                WorktreeIsolationManager(project_root=self.project_root)

    def test_init_fails_without_git_repo(self):
        """Test that initialization fails when not in a git repository."""
        # Don't initialize git repo
        with self.assertRaises(NotARepositoryError):
            WorktreeIsolationManager(project_root=self.project_root)

    def test_init_succeeds_with_git_repo(self):
        """Test that initialization succeeds with a valid git repository."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)
        self.assertIsNotNone(manager)
        self.assertEqual(manager._project_root, self.project_root)

    def test_create_session(self):
        """Test creating a new worktree session."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            info = loop.run_until_complete(
                manager.create_session(session_id="test-session")
            )

            self.assertEqual(info.session_id, "test-session")
            self.assertEqual(info.status, WorktreeStatus.CREATED)
            self.assertTrue(info.worktree_path.exists())
            self.assertTrue((info.worktree_path / ".git").exists())

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()

    def test_session_id_validation(self):
        """Test that session IDs are validated to prevent path traversal."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Malicious session_id with path traversal
            with self.assertRaises((WorktreeCreationError, ValueError)):
                loop.run_until_complete(
                    manager.create_session(session_id="../etc/passwd")
                )

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()

    def test_get_changes(self):
        """Test getting changes from a worktree session."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            info = loop.run_until_complete(
                manager.create_session(session_id="test-changes")
            )

            # Create a new file in the worktree
            new_file = info.worktree_path / "new_file.py"
            new_file.write_text("# New file content")

            # Get changes
            changes = loop.run_until_complete(manager.get_changes(info.session_id))

            # New untracked files appear in added_files, not changed_files
            # changed_files is from git diff which only shows tracked files
            self.assertGreater(len(changes.get("added_files", [])) + len(changes.get("changed_files", [])), 0)

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()

    def test_commit_session(self):
        """Test committing changes in a worktree session."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            info = loop.run_until_complete(
                manager.create_session(session_id="test-commit")
            )

            # Create a new file
            new_file = info.worktree_path / "new_file.py"
            new_file.write_text("# Content")

            # Commit changes
            commit_hash = loop.run_until_complete(
                manager.commit_session(info.session_id, message="Test commit")
            )

            self.assertIsNotNone(commit_hash)
            self.assertTrue(len(commit_hash) > 0)

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()

    def test_close_session(self):
        """Test closing a worktree session."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            info = loop.run_until_complete(
                manager.create_session(session_id="test-close")
            )

            worktree_path = info.worktree_path
            self.assertTrue(worktree_path.exists())

            # Close session
            result = loop.run_until_complete(
                manager.close_session(info.session_id)
            )

            self.assertTrue(result)
            # Worktree should be removed
            self.assertFalse(worktree_path.exists())

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()

    def test_list_sessions(self):
        """Test listing active sessions."""
        self._init_git_repo()

        manager = WorktreeIsolationManager(project_root=self.project_root)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create multiple sessions
            loop.run_until_complete(manager.create_session(session_id="session-1"))
            loop.run_until_complete(manager.create_session(session_id="session-2"))

            sessions = loop.run_until_complete(manager.list_sessions())

            self.assertEqual(len(sessions), 2)
            session_ids = {s.session_id for s in sessions}
            self.assertEqual(session_ids, {"session-1", "session-2"})

        finally:
            loop.run_until_complete(manager.cleanup_all())
            loop.close()


class TestWorktreeSandbox(unittest.TestCase):
    """Test the WorktreeSandbox SDK class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _init_git_repo(self):
        """Initialize a git repository in the temp directory."""
        import subprocess

        subprocess.run(["git", "init"], cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=self.temp_dir, check=True, capture_output=True)

        # Create initial commit
        test_file = self.project_root / "test.txt"
        test_file.write_text("Initial content")
        subprocess.run(["git", "add", "."], cwd=self.temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                      cwd=self.temp_dir, check=True, capture_output=True)

    def test_worktree_sandbox_creation(self):
        """Test creating a worktree sandbox."""
        self._init_git_repo()

        from sandbox.sdk.worktree_sandbox import WorktreeSandbox

        async def test():
            async with WorktreeSandbox.create(
                name="test-sandbox",
                project_root=self.project_root,
                auto_merge=False,
                auto_cleanup=True,
            ) as sandbox:
                self.assertTrue(sandbox.is_active)
                self.assertEqual(sandbox.name, "test-sandbox")
                self.assertIsNotNone(sandbox.worktree_path)

                # Execute code
                result = await sandbox.run("x = 42; print('Hello from worktree!')")
                self.assertFalse(result.has_error())
                self.assertIn("Hello from worktree!", await result.output())

        asyncio.run(test())

    def test_worktree_sandbox_file_isolation(self):
        """Test that worktree sandbox provides file isolation."""
        self._init_git_repo()

        from sandbox.sdk.worktree_sandbox import WorktreeSandbox

        async def test():
            # Create a file in the main repo
            main_file = self.project_root / "main_only.txt"
            main_file.write_text("Main repo file")

            async with WorktreeSandbox.create(
                name="isolation-test",
                project_root=self.project_root,
                auto_cleanup=True,
            ) as sandbox:
                # Create a file in the worktree
                worktree_file = sandbox.worktree_path / "worktree_only.txt"
                worktree_file.write_text("Worktree file")

                # Create file via sandbox execution
                await sandbox.run("open('executed_file.txt', 'w').write('Generated')")

                # Worktree file exists
                self.assertTrue(worktree_file.exists())

                # Check changes
                changes = await sandbox.get_changes()
                self.assertIn("worktree_only.txt", changes.get("added_files", []))

            # After cleanup, worktree file should not exist in main repo
            self.assertFalse((self.project_root / "worktree_only.txt").exists())

        asyncio.run(test())


class TestGetWorktreeManager(unittest.TestCase):
    """Test the get_worktree_manager singleton function."""

    def test_singleton_behavior(self):
        """Test that get_worktree_manager returns the same instance."""
        from sandbox.core.worktree_isolation import get_worktree_manager, _worktree_manager

        # Reset the global
        import sandbox.core.worktree_isolation as wim
        wim._worktree_manager = None

        manager1 = get_worktree_manager()
        manager2 = get_worktree_manager()

        self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()
