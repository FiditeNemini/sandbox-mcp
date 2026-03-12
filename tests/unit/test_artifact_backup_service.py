"""
Tests for ArtifactBackupService.

Tests verify:
- Path traversal protection (S3)
- Backup creation and rollback
- Service delegation pattern
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sandbox.core.artifact_backup_service import (
    ArtifactBackupService,
    get_backup_service,
)


class TestArtifactBackupService:
    """Tests for ArtifactBackupService."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def ctx(self, temp_dir):
        """Create a mock context with artifact paths."""
        ctx = MagicMock()
        ctx.project_root = Path(temp_dir)
        ctx.artifacts_dir = Path(temp_dir) / "artifacts"
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
        return ctx

    @pytest.fixture
    def service(self):
        """Create an ArtifactBackupService instance."""
        return ArtifactBackupService(max_backups=5)

    # --- Sanitization Tests (Security S3) ---

    def test_sanitize_valid_name(self, service):
        """Test that valid names pass sanitization."""
        assert service.sanitize_backup_name("valid_backup") == "valid_backup"
        assert service.sanitize_backup_name("backup-123") == "backup-123"
        assert service.sanitize_backup_name("test_456") == "test_456"
        assert service.sanitize_backup_name("Backup-Test_123") == "Backup-Test_123"

    def test_sanitize_rejects_path_traversal(self, service):
        """Test that path traversal attempts are rejected."""
        malicious_names = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "....//....//etc",
            "../escape",
            "backup/../../../etc",
        ]
        for name in malicious_names:
            with pytest.raises(ValueError, match="path traversal|'\\.\\."):
                service.sanitize_backup_name(name)

    def test_sanitize_rejects_path_separators(self, service):
        """Test that path separators are rejected."""
        with pytest.raises(ValueError, match="path separators"):
            service.sanitize_backup_name("backup/name")

        with pytest.raises(ValueError, match="path separators"):
            service.sanitize_backup_name("backup\\name")

    def test_sanitize_rejects_whitespace(self, service):
        """Test that whitespace is rejected."""
        for char in [" ", "\t", "\n", "\r"]:
            with pytest.raises(ValueError, match="whitespace"):
                service.sanitize_backup_name(f"backup{char}name")

    def test_sanitize_rejects_null_bytes(self, service):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError, match="null bytes"):
            service.sanitize_backup_name("backup\x00name")

    def test_sanitize_rejects_empty(self, service):
        """Test that empty names are rejected."""
        with pytest.raises(ValueError, match="empty"):
            service.sanitize_backup_name("")

    def test_sanitize_rejects_too_long(self, service):
        """Test that names over 128 characters are rejected."""
        long_name = "a" * 129
        with pytest.raises(ValueError, match="too long"):
            service.sanitize_backup_name(long_name)

    def test_sanitize_rejects_special_characters(self, service):
        """Test that special characters are rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            service.sanitize_backup_name("backup@name")

        with pytest.raises(ValueError, match="alphanumeric"):
            service.sanitize_backup_name("backup!name")

    # --- Backup Tests ---

    def test_backup_creates_directory(self, service, ctx):
        """Test that backup creates a backup directory."""
        # Create an artifact
        (ctx.artifacts_dir / "test.txt").write_text("test content")

        result = service.backup_artifacts(ctx)
        assert "backup_" in result
        assert Path(result).exists()

    def test_backup_with_name(self, service, ctx):
        """Test backup with custom name."""
        (ctx.artifacts_dir / "test.txt").write_text("test content")

        result = service.backup_artifacts(ctx, "my_backup")
        assert "my_backup_" in result
        assert Path(result).exists()

    def test_backup_sanitizes_name(self, service, ctx):
        """Test that backup name is sanitized."""
        (ctx.artifacts_dir / "test.txt").write_text("test content")

        result = service.backup_artifacts(ctx, "my-backup")
        assert "Invalid backup name" not in result

    def test_backup_rejects_malicious_name(self, service, ctx):
        """Test that malicious backup names are rejected."""
        (ctx.artifacts_dir / "test.txt").write_text("test content")

        result = service.backup_artifacts(ctx, "../../etc")
        assert "Invalid backup name" in result

    def test_backup_no_artifacts(self, service, ctx):
        """Test backup when no artifacts exist."""
        ctx.artifacts_dir = None
        result = service.backup_artifacts(ctx)
        assert "No artifacts directory" in result

    # --- Rollback Tests ---

    def test_rollback_success(self, service, ctx):
        """Test successful rollback."""
        # Create original artifact
        (ctx.artifacts_dir / "original.txt").write_text("original content")

        # Create backup
        backup_result = service.backup_artifacts(ctx, "test_backup")
        backup_name = Path(backup_result).name

        # Modify artifact
        (ctx.artifacts_dir / "original.txt").write_text("modified content")

        # Rollback
        result = service.rollback_artifacts(ctx, backup_name)
        assert "Successfully rolled back" in result
        assert (ctx.artifacts_dir / "original.txt").read_text() == "original content"

    def test_rollback_rejects_malicious_name(self, service, ctx):
        """Test that rollback rejects malicious names."""
        result = service.rollback_artifacts(ctx, "../../etc")
        assert "Invalid backup name" in result

    def test_rollback_nonexistent_backup(self, service, ctx):
        """Test rollback to nonexistent backup."""
        result = service.rollback_artifacts(ctx, "nonexistent_backup")
        assert "not found" in result

    def test_rollback_creates_pre_rollback_backup(self, service, ctx):
        """Test that rollback creates a pre-rollback backup."""
        (ctx.artifacts_dir / "test.txt").write_text("content")

        backup_result = service.backup_artifacts(ctx, "test_backup")
        backup_name = Path(backup_result).name

        (ctx.artifacts_dir / "test.txt").write_text("modified")

        service.rollback_artifacts(ctx, backup_name)

        # Should have pre_rollback backup
        backup_root = service.get_backup_root(ctx)
        pre_rollback_backups = [d for d in backup_root.iterdir() if d.name.startswith("pre_rollback")]
        assert len(pre_rollback_backups) >= 1

    # --- List Backups Tests ---

    def test_list_backups_empty(self, service, ctx):
        """Test listing backups when none exist."""
        backups = service.list_backups(ctx)
        assert backups == []

    def test_list_backups_returns_backups(self, service, ctx):
        """Test that list_backups returns created backups."""
        (ctx.artifacts_dir / "test.txt").write_text("content")

        service.backup_artifacts(ctx, "backup1")
        service.backup_artifacts(ctx, "backup2")

        backups = service.list_backups(ctx)
        assert len(backups) >= 2

    # --- Cleanup Tests ---

    def test_cleanup_removes_old_backups(self, service, ctx):
        """Test that cleanup removes old backups beyond max."""
        (ctx.artifacts_dir / "test.txt").write_text("content")

        # Create more backups than max (5)
        for i in range(7):
            service.backup_artifacts(ctx, f"backup_{i}")

        backups = service.list_backups(ctx)
        assert len(backups) <= 5

    # --- Get Backup Service ---

    def test_get_backup_service_singleton(self):
        """Test that get_backup_service returns singleton."""
        service1 = get_backup_service()
        service2 = get_backup_service()
        assert service1 is service2


class TestBackupServiceIntegration:
    """Integration tests for backup service with ExecutionContext."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    def test_stdio_context_uses_backup_service(self, temp_dir):
        """Test that stdio server ExecutionContext delegates to backup service."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext

        ctx = ExecutionContext()
        ctx.project_root = Path(temp_dir)
        ctx.artifacts_dir = Path(temp_dir) / "artifacts"
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Create an artifact
        (ctx.artifacts_dir / "test.txt").write_text("content")

        # Test backup delegates to service
        result = ctx.backup_artifacts("test_backup")
        assert "Invalid backup name" not in result
        assert Path(result).exists() or "backup" in result.lower()

    def test_stdio_context_backup_rejects_traversal(self, temp_dir):
        """Test that stdio context rejects path traversal in backup names."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext

        ctx = ExecutionContext()
        ctx.project_root = Path(temp_dir)
        ctx.artifacts_dir = Path(temp_dir) / "artifacts"
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)

        (ctx.artifacts_dir / "test.txt").write_text("content")

        result = ctx.backup_artifacts("../../etc")
        assert "Invalid backup name" in result

    def test_stdio_context_rollback_rejects_traversal(self, temp_dir):
        """Test that stdio context rejects path traversal in rollback."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext

        ctx = ExecutionContext()
        ctx.project_root = Path(temp_dir)
        ctx.artifacts_dir = Path(temp_dir) / "artifacts"
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)

        result = ctx.rollback_artifacts("../../etc")
        assert "Invalid backup name" in result
