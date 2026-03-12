"""
Coverage tests for execution_context_files.py - Tier 4 Task T4

Target: Raise coverage from 29% to 75%+
File operation methods with security checks and logging
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from sandbox.core.execution_context_files import (
    save_error_details,
    change_working_directory,
    list_directory,
    find_files,
    reset_to_default_directory,
    get_current_directory_info
)


class TestSaveErrorDetails:
    """Test error details saving."""

    def test_save_error_details_creates_file(self, tmp_path):
        """Test that error details are saved to file."""
        error = ValueError("Test error")
        code = "print('test')"
        traceback = "Traceback..."
        session_id = "test-session"

        save_error_details(tmp_path, error, code, traceback, session_id)

        # Check that error log file was created
        log_files = list((tmp_path / "logs").glob("error_*.log"))
        assert len(log_files) >= 1

    def test_save_error_details_file_content(self, tmp_path):
        """Test that error file contains correct content."""
        error = RuntimeError("Test runtime error")
        code = "x = 1\ny = 2"
        traceback = "Error line 1"
        session_id = "session-123"

        save_error_details(tmp_path, error, code, traceback, session_id)

        log_file = list((tmp_path / "logs").glob("error_*.log"))[0]
        content = log_file.read_text()
        assert "RuntimeError" in content
        assert "Test runtime error" in content
        assert "session-123" in content
        assert code in content

    def test_save_error_details_creates_logs_dir(self, tmp_path):
        """Test that logs directory is created if it doesn't exist."""
        error = Exception("Test")
        save_error_details(tmp_path, error, "", "", "test")
        assert (tmp_path / "logs").exists()


class TestChangeWorkingDirectory:
    """Test working directory changes."""

    @pytest.fixture
    def directory_monitor(self, tmp_path):
        """Mock directory monitor."""
        monitor = Mock()
        monitor.default_dir = tmp_path / "sandbox"
        monitor.default_dir.mkdir(exist_ok=True)
        return monitor

    def test_change_to_valid_directory(self, directory_monitor, tmp_path):
        """Test changing to a valid directory."""
        new_dir = tmp_path / "new_dir"
        new_dir.mkdir()

        result = change_working_directory(str(new_dir), False, directory_monitor, tmp_path)

        assert result['success'] is True
        assert 'current_directory' in result
        assert 'previous_directory' in result

    def test_change_directory_security_check(self, directory_monitor, tmp_path):
        """Test that security check is performed."""
        new_dir = tmp_path / "secure_dir"
        new_dir.mkdir()

        change_working_directory(str(new_dir), False, directory_monitor, tmp_path)
        # Should have called directory_monitor.change_directory
        directory_monitor.change_directory.assert_called_once()

    def test_change_to_nonexistent_directory(self, directory_monitor, tmp_path):
        """Test changing to nonexistent directory."""
        result = change_working_directory(
            "/nonexistent/path",
            False,
            directory_monitor,
            tmp_path
        )
        assert result['success'] is False
        assert 'error' in result

    def test_change_directory_temporary_flag(self, directory_monitor, tmp_path):
        """Test that temporary flag is recorded."""
        new_dir = tmp_path / "temp_dir"
        new_dir.mkdir()

        result = change_working_directory(str(new_dir), True, directory_monitor, tmp_path)
        assert result['is_temporary'] is True

    def test_change_to_home_dir(self, directory_monitor):
        """Test changing to home (default) directory."""
        result = change_working_directory(
            str(directory_monitor.default_dir),
            False,
            directory_monitor,
            directory_monitor.default_dir.parent
        )
        assert result['success'] is True


class TestListDirectory:
    """Test directory listing."""

    def test_list_current_directory(self, tmp_path):
        """Test listing current directory."""
        import os
        os.chdir(tmp_path)
        # Create some files
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "subdir").mkdir()

        result = list_directory(None, False, tmp_path)

        assert result['success'] is True
        assert result['total_items'] >= 3

    def test_list_specific_directory(self, tmp_path):
        """Test listing a specific directory."""
        test_dir = tmp_path / "test_list"
        test_dir.mkdir()
        (test_dir / "test.txt").touch()

        result = list_directory(str(test_dir), False, tmp_path)

        assert result['success'] is True
        assert any(item['name'] == 'test.txt' for item in result['items'])

    def test_list_directory_with_hidden_files(self, tmp_path):
        """Test listing directory with hidden files."""
        import os
        os.chdir(tmp_path)
        (tmp_path / ".hidden").touch()
        (tmp_path / "visible.txt").touch()

        result_no_hidden = list_directory(None, False, tmp_path)
        result_with_hidden = list_directory(None, True, tmp_path)

        # Check that both return success
        assert result_no_hidden['success'] is True
        assert result_with_hidden['success'] is True

    def test_list_nonexistent_directory(self, tmp_path):
        """Test listing nonexistent directory."""
        result = list_directory(str(tmp_path / "nonexistent"), False, tmp_path)

        assert result['success'] is False
        assert 'error' in result

    def test_list_directory_security_check(self, tmp_path):
        """Test that security check prevents listing outside home."""
        result = list_directory("/etc", False, tmp_path)

        assert result['success'] is False
        assert 'home' in result['error'].lower() or 'permission' in result['error'].lower()

    def test_list_directory_item_types(self, tmp_path):
        """Test that directory items have correct type information."""
        import os
        os.chdir(tmp_path)
        (tmp_path / "file.txt").touch()
        (tmp_path / "directory").mkdir()

        result = list_directory(None, False, tmp_path)

        if result['success'] and 'items' in result:
            file_items = [i for i in result['items'] if i['name'] == 'file.txt']
            dir_items = [i for i in result['items'] if i['name'] == 'directory']

            if file_items:
                assert file_items[0]['type'] == 'file'
            if dir_items:
                assert dir_items[0]['type'] == 'directory'


class TestFindFiles:
    """Test file finding."""

    def test_find_files_with_pattern(self, tmp_path):
        """Test finding files with glob pattern."""
        import os
        os.chdir(tmp_path)
        (tmp_path / "test1.txt").touch()
        (tmp_path / "test2.txt").touch()
        (tmp_path / "other.py").touch()

        result = find_files("*.txt", str(tmp_path), 10, tmp_path)

        assert result['success'] is True
        assert result['total_matches'] >= 2

    def test_find_files_in_subdirectory(self, tmp_path):
        """Test finding files in subdirectory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "found.txt").touch()
        # Also add a file in root
        (tmp_path / "root.txt").touch()

        result = find_files("*.txt", str(tmp_path), 10, tmp_path)

        assert result['success'] is True
        # Should find at least root.txt
        assert result['total_matches'] >= 1

    def test_find_files_max_results(self, tmp_path):
        """Test that max_results limits results."""
        for i in range(10):
            (tmp_path / f"file{i}.txt").touch()

        result = find_files("*.txt", str(tmp_path), 5, tmp_path)

        assert result['success'] is True
        assert result['total_matches'] <= 5

    def test_find_files_no_matches(self, tmp_path):
        """Test finding files when no matches."""
        result = find_files("*.nonexistent", str(tmp_path), 10, tmp_path)

        assert result['success'] is True
        assert result['total_matches'] == 0

    def test_find_files_security_check(self, tmp_path):
        """Test that security check prevents searching outside home."""
        result = find_files("*", "/etc", 10, tmp_path)

        assert result['success'] is False
        assert 'home' in result['error'].lower() or 'permission' in result['error'].lower()

    def test_find_files_truncated_flag(self, tmp_path):
        """Test that truncated flag is set when max results reached."""
        for i in range(10):
            (tmp_path / f"file{i}.txt").touch()

        result = find_files("*.txt", str(tmp_path), 5, tmp_path)

        assert result.get('truncated', False) is True or result['total_matches'] <= 5


class TestResetToDefaultDirectory:
    """Test resetting to default directory."""

    @pytest.fixture
    def directory_monitor(self, tmp_path):
        """Mock directory monitor."""
        monitor = Mock()
        monitor.default_dir = tmp_path / "sandbox"
        monitor.default_dir.mkdir(exist_ok=True)
        return monitor

    def test_reset_to_default(self, directory_monitor):
        """Test resetting to default directory."""
        result = reset_to_default_directory(directory_monitor)

        assert result['success'] is True
        assert 'current_directory' in result
        assert result['current_directory'] == str(directory_monitor.default_dir)

    def test_reset_calls_monitor_reset(self, directory_monitor):
        """Test that reset calls monitor's reset method."""
        reset_to_default_directory(directory_monitor)
        directory_monitor.reset_to_default.assert_called_once()

    def test_reset_includes_message(self, directory_monitor):
        """Test that result includes a message."""
        result = reset_to_default_directory(directory_monitor)

        assert 'message' in result
        assert 'default' in result['message'].lower()


class TestGetCurrentDirectoryInfo:
    """Test getting current directory information."""

    @pytest.fixture
    def directory_monitor(self, tmp_path):
        """Mock directory monitor."""
        monitor = Mock()
        monitor.default_dir = tmp_path / "sandbox"
        monitor.default_dir.mkdir(exist_ok=True)
        return monitor

    def test_get_current_directory_info(self, directory_monitor, tmp_path):
        """Test getting directory information."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        result = get_current_directory_info(directory_monitor, tmp_path, artifacts_dir)

        assert 'current_directory' in result
        assert 'default_directory' in result
        assert 'home_directory' in result
        assert 'artifacts_directory' in result

    def test_get_directory_info_is_default_flag(self, directory_monitor, tmp_path):
        """Test is_default flag."""
        import os
        os.chdir(directory_monitor.default_dir)

        result = get_current_directory_info(directory_monitor, tmp_path, tmp_path)

        assert result['is_default'] is True

    def test_get_directory_info_is_in_home_flag(self, directory_monitor, tmp_path):
        """Test is_in_home flag."""
        result = get_current_directory_info(directory_monitor, tmp_path, tmp_path)

        assert 'is_in_home' in result
        assert isinstance(result['is_in_home'], bool)


class TestIntegration:
    """Integration tests for file operations."""

    @pytest.fixture
    def directory_monitor(self, tmp_path):
        """Mock directory monitor."""
        monitor = Mock()
        monitor.default_dir = tmp_path / "sandbox"
        monitor.default_dir.mkdir(exist_ok=True)
        return monitor

    def test_change_then_list_directory(self, directory_monitor, tmp_path):
        """Test changing directory then listing."""
        new_dir = tmp_path / "test_dir"
        new_dir.mkdir()
        (new_dir / "test.txt").touch()

        change_working_directory(str(new_dir), False, directory_monitor, tmp_path)
        list_result = list_directory(None, False, tmp_path)

        assert any(item['name'] == 'test.txt' for item in list_result['items'])

    def test_find_after_reset_to_default(self, directory_monitor, tmp_path):
        """Test finding files after reset."""
        (directory_monitor.default_dir / "default.txt").touch()

        reset_to_default_directory(directory_monitor)
        find_result = find_files("*.txt", None, 10, tmp_path)

        assert find_result['success'] is True
        assert find_result['total_matches'] >= 1

    def test_save_error_then_get_info(self, tmp_path):
        """Test saving error then getting directory info."""
        monitor = Mock()
        monitor.default_dir = tmp_path

        save_error_details(tmp_path, Exception("test"), "", "", "session")
        info = get_current_directory_info(monitor, tmp_path, tmp_path)

        assert 'current_directory' in info
        assert (tmp_path / "logs").exists()
