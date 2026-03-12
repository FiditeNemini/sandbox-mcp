"""
Tests for unified patching utilities.

Following TDD: These tests should FAIL initially, then pass after
implementing src/sandbox/core/patching.py
"""

import pytest


class TestPatchingUtilities:
    """Test unified patching utilities."""

    def test_patching_module_exists(self):
        """Test that patching module can be imported."""
        # This test should FAIL initially (module doesn't exist)
        from sandbox.core.patching import PatchManager
        assert PatchManager is not None

    def test_patch_manager_initialization(self):
        """Test that PatchManager can be instantiated."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        assert manager is not None

    def test_patch_manager_has_matplotlib_patch(self):
        """Test that patch manager has matplotlib patch method."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        assert hasattr(manager, 'patch_matplotlib')

    def test_patch_manager_has_pil_patch(self):
        """Test that patch manager has PIL patch method."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        assert hasattr(manager, 'patch_pil') or hasattr(manager, 'patch PIL')

    def test_matplotlib_backend_configuration(self):
        """Test that matplotlib backend can be configured."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        
        # Should be able to configure backend
        backend = manager.configure_matplotlib_backend('Agg')
        assert backend == 'Agg'

    def test_pil_image_save_patch(self):
        """Test that PIL image save can be patched."""
        from sandbox.core.patching import PatchManager
        from pathlib import Path
        import tempfile
        
        manager = PatchManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            
            # Apply patch
            manager.patch_pil(artifacts_dir)
            
            # PIL should be patched (test will verify after implementation)
            assert True  # Placeholder - actual test after implementation

    def test_patch_manager_cleanup(self):
        """Test that patch manager has cleanup method."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        
        # Should have cleanup/unpatch method
        assert hasattr(manager, 'cleanup') or hasattr(manager, 'unpatch_all')


class TestPatchingIntegration:
    """Test patching integration with execution context."""

    def test_patch_manager_works_with_artifacts_dir(self):
        """Test that patch manager works with artifacts directory."""
        from sandbox.core.patching import PatchManager
        from sandbox.core.execution_services import ExecutionContextService
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            
            manager = PatchManager()
            execution_service = ExecutionContextService()
            context = execution_service.create_context()
            
            # Should be able to apply patches with artifacts dir
            manager.patch_matplotlib(artifacts_dir)
            
            assert True  # Placeholder
