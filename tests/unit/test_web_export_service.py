"""
Tests for web export service module.

Following TDD: These tests define the expected behavior of the web export service.
"""

import pytest
import pytest_asyncio
import tempfile
import shutil
from pathlib import Path


@pytest.mark.asyncio
class TestWebExportService:
    """Test unified web export service."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create a temporary artifacts directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_web_export_service_module_exists(self):
        """Test that web_export_service module can be imported."""
        from sandbox.server.web_export_service import WebExportService
        assert WebExportService is not None

    async def test_web_export_service_initialization(self):
        """Test that WebExportService can be instantiated."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert service is not None
        assert service.artifacts_dir is None

    async def test_web_export_service_initialization_with_dir(self, temp_artifacts_dir):
        """Test that WebExportService can be instantiated with artifacts directory."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        assert service is not None
        assert service.artifacts_dir == temp_artifacts_dir

    async def test_web_export_service_has_export_flask_app(self):
        """Test that web export service has export_flask_app method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'export_flask_app')

    async def test_web_export_service_has_export_streamlit_app(self):
        """Test that web export service has export_streamlit_app method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'export_streamlit_app')

    async def test_web_export_service_has_export_web_app(self):
        """Test that web export service has export_web_app method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'export_web_app')

    async def test_web_export_service_has_list_exports(self):
        """Test that web export service has list_web_app_exports method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'list_web_app_exports')

    async def test_web_export_service_has_get_export_details(self):
        """Test that web export service has get_export_details method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'get_export_details')

    async def test_web_export_service_has_cleanup_export(self):
        """Test that web export service has cleanup_web_app_export method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'cleanup_web_app_export')

    async def test_web_export_service_has_build_docker_image(self):
        """Test that web export service has build_docker_image method."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        assert hasattr(service, 'build_docker_image')

    async def test_export_flask_app_without_artifacts_dir(self):
        """Test that export fails gracefully without artifacts directory."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        result = service.export_flask_app("print('hello')")

        assert result['success'] is False
        assert 'error' in result
        assert 'No artifacts directory' in result['error']

    async def test_export_streamlit_app_without_artifacts_dir(self):
        """Test that export fails gracefully without artifacts directory."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService()
        result = service.export_streamlit_app("print('hello')")

        assert result['success'] is False
        assert 'error' in result
        assert 'No artifacts directory' in result['error']

    async def test_export_web_app_unsupported_type(self, temp_artifacts_dir):
        """Test that export fails for unsupported app types."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_web_app("print('hello')", app_type='django')

        assert result['success'] is False
        assert 'Unsupported app type' in result['error']

    async def test_export_flask_app_creates_files(self, temp_artifacts_dir):
        """Test that Flask export creates expected files."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        
        result = service.export_flask_app(flask_code, export_name="test_flask")

        assert result['success'] is True
        assert result['export_name'] == "test_flask"
        assert len(result['files_created']) > 0
        
        # Check that expected files exist
        export_dir = Path(result['export_dir'])
        assert (export_dir / "app.py").exists()
        assert (export_dir / "requirements.txt").exists()
        assert (export_dir / "Dockerfile").exists()
        assert (export_dir / "docker-compose.yml").exists()
        assert (export_dir / "README.md").exists()

    async def test_export_streamlit_app_creates_files(self, temp_artifacts_dir):
        """Test that Streamlit export creates expected files."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        streamlit_code = "import streamlit as st\nst.title('Hello')"
        
        result = service.export_streamlit_app(streamlit_code, export_name="test_streamlit")

        assert result['success'] is True
        assert result['export_name'] == "test_streamlit"
        assert len(result['files_created']) > 0
        
        # Check that expected files exist
        export_dir = Path(result['export_dir'])
        assert (export_dir / "app.py").exists()
        assert (export_dir / "requirements.txt").exists()
        assert (export_dir / "Dockerfile").exists()
        assert (export_dir / "docker-compose.yml").exists()
        assert (export_dir / "README.md").exists()

    async def test_export_web_app_flask(self, temp_artifacts_dir):
        """Test that export_web_app works for Flask type."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        
        result = service.export_web_app(flask_code, app_type='flask', export_name="test_web_flask")

        assert result['success'] is True
        assert result['export_name'] == "test_web_flask"

    async def test_export_web_app_streamlit(self, temp_artifacts_dir):
        """Test that export_web_app works for Streamlit type."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        streamlit_code = "import streamlit as st\nst.title('Hello')"
        
        result = service.export_web_app(streamlit_code, app_type='streamlit', export_name="test_web_streamlit")

        assert result['success'] is True
        assert result['export_name'] == "test_web_streamlit"

    async def test_list_exports_empty(self, temp_artifacts_dir):
        """Test listing exports when none exist."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.list_web_app_exports()

        # Status can be 'success' or 'no_exports' depending on whether exports dir exists
        assert result['status'] in ('success', 'no_exports')
        # Check total_exports if present (may not be in 'no_exports' case)
        if 'total_exports' in result:
            assert result['total_exports'] == 0
        assert result['exports'] == []

    async def test_list_exports_with_exports(self, temp_artifacts_dir):
        """Test listing exports when exports exist."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Create an export
        service.export_flask_app("print('hello')", export_name="test_list")
        
        result = service.list_web_app_exports()

        assert result['status'] == 'success'
        assert result['total_exports'] == 1
        assert len(result['exports']) == 1
        assert result['exports'][0]['name'] == "test_list"

    async def test_get_export_details(self, temp_artifacts_dir):
        """Test getting details of a specific export."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Create an export
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        service.export_flask_app(flask_code, export_name="test_details")
        
        result = service.get_export_details("test_details")

        assert result['status'] == 'success'
        assert 'export_info' in result
        assert result['export_info']['name'] == "test_details"
        assert result['export_info']['app_type'] == 'flask'

    async def test_get_export_details_not_found(self, temp_artifacts_dir):
        """Test getting details of non-existent export."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.get_export_details("nonexistent")

        assert result['status'] == 'error'
        assert 'not found' in result['message']

    async def test_cleanup_export(self, temp_artifacts_dir):
        """Test cleaning up an export."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Create an export
        service.export_flask_app("print('hello')", export_name="test_cleanup")
        
        # Verify it exists
        exports_before = service.list_web_app_exports()
        assert exports_before['total_exports'] == 1
        
        # Clean it up
        result = service.cleanup_web_app_export("test_cleanup")
        
        assert result['status'] == 'success'
        
        # Verify it's gone
        exports_after = service.list_web_app_exports()
        assert exports_after['total_exports'] == 0

    async def test_cleanup_export_not_found(self, temp_artifacts_dir):
        """Test cleaning up non-existent export."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.cleanup_web_app_export("nonexistent")

        assert result['status'] == 'error'
        assert 'not found' in result['message']

    async def test_build_docker_image_not_found(self, temp_artifacts_dir):
        """Test building Docker image for non-existent export."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.build_docker_image("nonexistent")

        assert result['status'] == 'error'
        assert 'not found' in result['message']

    async def test_build_docker_image_no_dockerfile(self, temp_artifacts_dir):
        """Test building Docker image when Dockerfile is missing."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Create export directory without Dockerfile
        export_dir = temp_artifacts_dir / "exports" / "test_no_dockerfile"
        export_dir.mkdir(parents=True)
        
        result = service.build_docker_image("test_no_dockerfile")

        assert result['status'] == 'error'
        assert 'No Dockerfile' in result['message']

    async def test_get_singleton_service(self, temp_artifacts_dir):
        """Test getting singleton service instance."""
        from sandbox.server.web_export_service import get_web_export_service

        service1 = get_web_export_service(temp_artifacts_dir)
        service2 = get_web_export_service(temp_artifacts_dir)

        assert service1 is service2


@pytest.mark.asyncio
class TestWebExportServiceSecurity:
    """Security tests for web export service."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create a temporary artifacts directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_path_traversal_prevention(self, temp_artifacts_dir):
        """Test that path traversal attacks are prevented."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Try various path traversal attacks
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\..\\etc\\passwd",
            "....//....//etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\System32",
        ]
        
        for malicious_name in malicious_names:
            result = service.export_flask_app("print('hello')", export_name=malicious_name)
            # Should either fail or sanitize the name (not use the malicious path)
            if result.get('success'):
                # If it succeeded, verify the export_dir doesn't contain path traversal
                assert '..' not in result['export_dir']
                assert result['export_dir'].startswith(str(temp_artifacts_dir))

    async def test_export_name_validation_empty(self, temp_artifacts_dir):
        """Test that empty export names generate default names."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("print('hello')", export_name="")
        
        # Empty string should generate a default name (this is acceptable behavior)
        # The service should handle this gracefully by generating a unique name
        assert result['success'] is True
        assert 'export_name' in result
        assert result['export_name'].startswith('flask_app_')

    async def test_export_name_validation_whitespace(self, temp_artifacts_dir):
        """Test that whitespace-only export names are rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("print('hello')", export_name="   ")
        
        assert result['success'] is False
        assert 'error' in result

    async def test_export_name_validation_too_long(self, temp_artifacts_dir):
        """Test that overly long export names are rejected."""
        from sandbox.server.web_export_service import WebExportService, MAX_EXPORT_NAME_LENGTH

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        long_name = "a" * (MAX_EXPORT_NAME_LENGTH + 1)
        result = service.export_flask_app("print('hello')", export_name=long_name)
        
        assert result['success'] is False
        assert 'error' in result

    async def test_export_name_validation_special_chars(self, temp_artifacts_dir):
        """Test that special characters in export names are rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Test dangerous characters
        dangerous_names = [
            "test<name",
            "test>name",
            "test:name",
            'test"name',
            "test|name",
            "test?name",
            "test*name",
            "test\x00name",
        ]
        
        for dangerous_name in dangerous_names:
            result = service.export_flask_app("print('hello')", export_name=dangerous_name)
            # Should either fail or sanitize
            if result.get('success'):
                # Verify sanitization occurred
                for char in ['<', '>', ':', '"', '|', '?', '*']:
                    assert char not in result['export_name']

    async def test_export_name_validation_hidden_files(self, temp_artifacts_dir):
        """Test that hidden file/directory names are rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("print('hello')", export_name=".hidden")
        
        assert result['success'] is False
        assert 'error' in result

    async def test_export_name_validation_reserved_names(self, temp_artifacts_dir):
        """Test that reserved names are rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        reserved_names = ['.', '..', 'con', 'prn', 'aux', 'nul', 'com1', 'lpt1']
        
        for reserved_name in reserved_names:
            result = service.export_flask_app("print('hello')", export_name=reserved_name)
            assert result['success'] is False
            assert 'error' in result

    async def test_code_validation_empty(self, temp_artifacts_dir):
        """Test that empty code is rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("")
        
        assert result['success'] is False
        assert 'error' in result

    async def test_code_validation_whitespace_only(self, temp_artifacts_dir):
        """Test that whitespace-only code is rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("   \n\t  ")
        
        assert result['success'] is False
        assert 'error' in result

    async def test_code_validation_null_byte(self, temp_artifacts_dir):
        """Test that code with null bytes is rejected."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.export_flask_app("print('hello')\x00print('world')")
        
        assert result['success'] is False
        assert 'error' in result

    async def test_docker_image_name_sanitization(self, temp_artifacts_dir):
        """Test that Docker image names are properly sanitized."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Test names that need sanitization
        test_cases = [
            ("Test_Name", "sandbox-test-name"),  # Uppercase and underscore
            ("test.name", "sandbox-test-name"),  # Dot
            ("test--name", "sandbox-test--name"),  # Multiple hyphens (allowed)
            ("test!name", "sandbox-testname"),  # Special char
        ]
        
        for input_name, expected_prefix in test_cases:
            result = service.export_flask_app("print('hello')", export_name=input_name)
            # Export should succeed even if name is sanitized
            if result.get('success') and result.get('docker_image'):
                # Docker image name should be lowercase and sanitized
                docker_name = result['docker_image']
                assert docker_name == docker_name.lower()
                assert not any(c in docker_name for c in ['_', '.', '!', '@', '#'])

    async def test_symlink_export_dir_rejected(self, temp_artifacts_dir):
        """Test that symlink exports directory is rejected."""
        from sandbox.server.web_export_service import WebExportService

        # Create a real directory elsewhere
        real_dir = temp_artifacts_dir / "real_exports"
        real_dir.mkdir()
        
        # Create symlink to it
        symlink_dir = temp_artifacts_dir / "exports"
        symlink_dir.symlink_to(real_dir)
        
        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        result = service.list_web_app_exports()
        
        # Should reject symlink
        assert result.get('status') == 'error'
        assert 'symlink' in result.get('message', '').lower()

    async def test_name_collision_handling(self, temp_artifacts_dir):
        """Test that name collisions are handled gracefully."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Create first export
        result1 = service.export_flask_app("print('hello1')", export_name="collision_test")
        assert result1['success'] is True
        
        # Create second export with same name
        result2 = service.export_flask_app("print('hello2')", export_name="collision_test")
        assert result2['success'] is True
        
        # Names should be different due to collision handling
        assert result1['export_name'] != result2['export_name']
        assert result2['export_name'].startswith("collision_test")

    async def test_get_export_details_path_traversal(self, temp_artifacts_dir):
        """Test that get_export_details prevents path traversal."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Try path traversal
        result = service.get_export_details("../../../etc/passwd")
        
        # Should fail due to validation
        assert result['status'] == 'error'

    async def test_cleanup_export_path_traversal(self, temp_artifacts_dir):
        """Test that cleanup_export prevents path traversal."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)
        
        # Try path traversal
        result = service.cleanup_web_app_export("../../../etc/passwd")
        
        # Should fail due to validation
        assert result['status'] == 'error'

    async def test_build_docker_image_path_traversal(self, temp_artifacts_dir):
        """Test that build_docker_image prevents path traversal."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Try path traversal
        result = service.build_docker_image("../../../etc/passwd")

        # Should fail due to validation
        assert result['status'] == 'error'


class TestWebExportServiceDiskSpace:
    """Test disk space validation for DoS prevention."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create a temporary artifacts directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_check_disk_space_sufficient(self, temp_artifacts_dir):
        """Test disk space check passes when space available."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        ok, message = service._check_disk_space(temp_artifacts_dir, 1024)
        assert ok is True
        assert message == "OK"

    def test_check_disk_space_insufficient(self, temp_artifacts_dir):
        """Test disk space check fails when space insufficient."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Request impossibly large space (1PB)
        ok, message = service._check_disk_space(
            temp_artifacts_dir,
            1024 * 1024 * 1024 * 1024 * 1024
        )
        assert ok is False
        assert "Insufficient disk space" in message

    def test_estimate_export_size(self, temp_artifacts_dir):
        """Test export size estimation."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Small code
        small_code = "print('hello')"
        size = service._estimate_export_size(small_code, 'flask')
        assert size > 0
        assert size < 10000  # Should be small

        # Large code
        large_code = "x = '" + "A" * 10000 + "'"
        large_size = service._estimate_export_size(large_code, 'flask')
        assert large_size > size  # Larger code = larger estimate

    def test_export_fails_on_insufficient_space(self, temp_artifacts_dir, monkeypatch):
        """Test export fails gracefully when disk space insufficient."""
        from sandbox.server.web_export_service import WebExportService
        import shutil

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Mock disk_usage to report critically high usage (95%)
        # But enough free space to pass the size check
        mock_usage = type('Usage', (), {
            'total': 10000000000,  # 10GB total
            'used': 9500000000,    # 9.5GB used (95%)
            'free': 500000000      # 500MB free (enough for export, but triggers 90% warning)
        })()

        monkeypatch.setattr(shutil, 'disk_usage', lambda p: mock_usage)

        result = service.export_flask_app("print('hello')", export_name="test")

        assert result['success'] is False
        assert 'Disk usage critical' in result['error']
        assert 'estimated_size' in result

    def test_export_size_limit_enforced(self, temp_artifacts_dir):
        """Test that export size limit is enforced."""
        from sandbox.server.web_export_service import WebExportService, MAX_EXPORT_SIZE_BYTES

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Create code that would exceed limit when estimated
        # The estimate adds ~1KB overhead, so we need code close to the limit
        huge_code = "x = '" + "A" * (MAX_EXPORT_SIZE_BYTES - 5000) + "'"

        result = service.export_flask_app(huge_code, export_name="huge_test")

        assert result['success'] is False
        assert 'exceeds maximum' in result['error']


@pytest.mark.asyncio
class TestWebExportServiceIntegration:
    """Integration tests for web export service."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create a temporary artifacts directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_full_export_lifecycle(self, temp_artifacts_dir):
        """Test complete export lifecycle: create, list, get details, cleanup."""
        from sandbox.server.web_export_service import WebExportService

        service = WebExportService(artifacts_dir=temp_artifacts_dir)

        # Create export
        flask_code = "from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef hello():\n    return 'Hello'"
        export_result = service.export_flask_app(flask_code, export_name="lifecycle_test")
        assert export_result['success'] is True

        # List exports
        list_result = service.list_web_app_exports()
        assert list_result['total_exports'] == 1

        # Get details
        details_result = service.get_export_details("lifecycle_test")
        assert details_result['status'] == 'success'
        assert 'app.py' in details_result['export_info']['files']

        # Cleanup
        cleanup_result = service.cleanup_web_app_export("lifecycle_test")
        assert cleanup_result['status'] == 'success'

        # Verify cleanup
        final_list = service.list_web_app_exports()
        assert final_list['total_exports'] == 0
