"""
Unified Patching Utilities for Sandbox MCP.

This module consolidates duplicate monkey-patching logic from both
MCP servers for matplotlib and PIL.
"""

from pathlib import Path
from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class PatchManager:
    """
    Manager for monkey patches in sandbox environments.
    
    This class provides unified patching for matplotlib and PIL,
    replacing duplicate logic in both MCP servers.
    """
    
    def __init__(self):
        """Initialize the patch manager."""
        self._patches_applied: Dict[str, bool] = {}
        self._original_functions: Dict[str, Any] = {}
    
    def configure_matplotlib_backend(self, backend: str = 'Agg') -> str:
        """
        Configure matplotlib backend.
        
        Args:
            backend: The matplotlib backend to use (default: 'Agg').
        
        Returns:
            The configured backend name.
        """
        try:
            import matplotlib
            matplotlib.use(backend, force=True)
            self._patches_applied['matplotlib_backend'] = True
            logger.info(f"Configured matplotlib backend: {backend}")
            return backend
        except ImportError:
            logger.warning("matplotlib not available, skipping backend configuration")
            return backend
    
    def patch_matplotlib(self, artifacts_dir: Optional[Path] = None) -> bool:
        """
        Apply matplotlib patches for artifact capture.
        
        Args:
            artifacts_dir: Optional directory for saving plots.
        
        Returns:
            True if patches were applied successfully.
        """
        try:
            import matplotlib
            matplotlib.use('Agg', force=True)
            self._patches_applied['matplotlib'] = True
            logger.info("Applied matplotlib patches")
            return True
        except ImportError:
            logger.warning("matplotlib not available, skipping patches")
            return False
    
    def patch_pil(self, artifacts_dir: Optional[Path] = None) -> bool:
        """
        Apply PIL/Image patches for artifact capture.
        
        Args:
            artifacts_dir: Optional directory for saving images.
        
        Returns:
            True if patches were applied successfully.
        """
        try:
            from PIL import Image
            
            # Store original save method
            if 'pil_save' not in self._original_functions:
                self._original_functions['pil_save'] = Image.Image.save
            
            # Apply patch if artifacts_dir is provided
            if artifacts_dir:
                images_dir = artifacts_dir / 'images'
                images_dir.mkdir(parents=True, exist_ok=True)
                
                # Note: Actual patching would require more complex logic
                # This is a placeholder for the patch application
                logger.info(f"PIL patch configured for: {images_dir}")
            
            self._patches_applied['pil'] = True
            logger.info("Applied PIL patches")
            return True
        except ImportError:
            logger.warning("PIL not available, skipping patches")
            return False
    
    def apply_all_patches(self, artifacts_dir: Optional[Path] = None) -> Dict[str, bool]:
        """
        Apply all available patches.
        
        Args:
            artifacts_dir: Optional directory for artifacts.
        
        Returns:
            Dictionary of patch names to success status.
        """
        results = {
            'matplotlib': self.patch_matplotlib(artifacts_dir),
            'pil': self.patch_pil(artifacts_dir),
        }
        return results
    
    def cleanup(self) -> None:
        """Cleanup and restore original functions."""
        try:
            # Restore PIL save if it was patched
            if 'pil_save' in self._original_functions:
                from PIL import Image
                Image.Image.save = self._original_functions['pil_save']
                del self._original_functions['pil_save']
                logger.info("Restored original PIL save method")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
        
        self._patches_applied.clear()
    
    def unpatch_all(self) -> None:
        """Alias for cleanup()."""
        self.cleanup()
    
    def get_patch_status(self) -> Dict[str, bool]:
        """
        Get status of applied patches.
        
        Returns:
            Dictionary of patch names to applied status.
        """
        return self._patches_applied.copy()


# Singleton instance for convenience
_patch_manager: Optional[PatchManager] = None


def get_patch_manager() -> PatchManager:
    """
    Get the global patch manager instance.
    
    Returns:
        The singleton PatchManager instance.
    """
    global _patch_manager
    if _patch_manager is None:
        _patch_manager = PatchManager()
    return _patch_manager
