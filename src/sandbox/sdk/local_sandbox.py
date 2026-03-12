"""
Local sandbox implementation for the enhanced Sandbox SDK.
"""

import io
import json
import sys
import os
import traceback
import uuid
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_sandbox import BaseSandbox
from .execution import Execution
from .config import SandboxConfig, IsolationLevel
from ..core.execution_context import PersistentExecutionContext
from ..core.patching import get_patch_manager
from ..core.worktree_manager import WorktreeManager, find_git_repo

logger = logging.getLogger(__name__)


class LocalSandbox(BaseSandbox):
    """
    Local sandbox implementation that uses the existing MCP server functionality.

    This provides secure local execution with artifact capture and virtual environment support.
    Supports multiple isolation levels: in-process, process pool, worktree, and container.
    """

    def __init__(self, config: Optional[SandboxConfig] = None, **kwargs):
        """
        Initialize a local sandbox instance.

        Args:
            config: SandboxConfig with isolation settings
            **kwargs: Additional keyword arguments passed to BaseSandbox
        """
        # Force remote=False for local sandboxes
        kwargs["remote"] = False
        super().__init__(**kwargs)

        # Store config for isolation settings
        self._config = config or SandboxConfig()

        # Initialize local execution context with persistence
        self._execution_context = PersistentExecutionContext()
        self._execution_globals = self._execution_context.globals_dict

        # Apply monkey patches for artifact capture using core service
        patch_manager = get_patch_manager()
        patch_manager.patch_matplotlib()
        patch_manager.patch_pil()

        # Process pool for isolated execution (lazy loaded)
        self._process_pool = None

        # Worktree isolation support
        self._worktree_manager: Optional[WorktreeManager] = None
        self._worktree_path: Optional[Path] = None
        self._worktree_branch: Optional[str] = None
        self._original_cwd: Optional[Path] = None

    async def get_default_image(self) -> str:
        """
        Get the default Docker image for local sandbox (not used in local execution).
        """
        return "local-python"

    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
    ) -> None:
        """
        Start the local sandbox.

        For local sandboxes, this primarily sets up the execution environment.
        If worktree isolation is enabled, creates a git worktree for this session.
        """
        if self._is_started:
            return

        # Setup worktree isolation if configured
        if self._config.isolation_level == IsolationLevel.WORKTREE:
            await self._setup_worktree()

        # Already set up in PersistentExecutionContext
        # No additional setup needed for persistent context

        self._is_started = True

    async def _setup_worktree(self) -> None:
        """
        Setup worktree-based isolation.

        Creates a git worktree for the session and updates the working directory.
        """
        repo_root = find_git_repo()
        if repo_root is None:
            raise ValueError(
                "Worktree isolation requires a git repository. "
                "Initialize one with 'git init' or run from within an existing repo."
            )

        self._worktree_manager = WorktreeManager(repo_root)

        try:
            worktree_path, branch = self._worktree_manager.create_worktree(
                session_id=self._name,
                base_branch=self._config.worktree_base_branch,
            )

            self._worktree_path = worktree_path
            self._worktree_branch = branch
            self._original_cwd = Path.cwd()

            logger.info(
                f"Created worktree for sandbox: {worktree_path} "
                f"(branch: {branch})"
            )

        except Exception as e:
            logger.error(f"Failed to setup worktree: {e}")
            raise

    async def _cleanup_worktree(self) -> None:
        """
        Cleanup worktree after session.

        Handles merging and deletion based on configuration.
        """
        if self._worktree_manager is None:
            return

        try:
            # Check if there are changes
            status = self._worktree_manager.get_worktree_status(self._name)

            if status.get("has_changes"):
                if self._config.auto_merge_on_close:
                    # Commit changes first
                    self._worktree_manager.commit_worktree_changes(
                        self._name,
                        message=self._config.worktree_commit_message
                        or f"Sandbox session: {self._name}",
                    )

                    # Merge back to main branch
                    target_branch = (
                        self._config.worktree_base_branch
                        or self._worktree_manager._get_current_branch()
                        or "main"
                    )
                    success = self._worktree_manager.merge_worktree(
                        session_id=self._name,
                        target_branch=target_branch,
                        delete_after=self._config.auto_delete_worktree,
                        commit_message=self._config.worktree_commit_message,
                    )

                    if success:
                        logger.info(f"Merged worktree changes to {target_branch}")
                    else:
                        logger.warning(
                            f"Failed to merge worktree, keeping it for manual review"
                        )
                        self._worktree_manager.delete_worktree(self._name)
                elif self._config.auto_delete_worktree:
                    # Just delete without merging
                    self._worktree_manager.delete_worktree(self._name)
                    logger.info(f"Deleted worktree without merging")
                else:
                    # Leave worktree for manual review
                    logger.info(
                        f"Worktree preserved at: {self._worktree_path} "
                        f"(branch: {self._worktree_branch})"
                    )
            elif self._config.auto_delete_worktree:
                # No changes, just delete
                self._worktree_manager.delete_worktree(self._name)

        except Exception as e:
            logger.error(f"Error during worktree cleanup: {e}")
        finally:
            self._worktree_manager = None
            self._worktree_path = None
            self._worktree_branch = None
            self._original_cwd = None

    async def stop(self) -> None:
        """
        Stop the local sandbox and clean up resources.

        If worktree isolation was enabled, handles merge/deletion based on config.
        If process pool was used, cleans up the process pool.
        """
        if not self._is_started:
            return

        # Clean up process pool if using process pool isolation
        if self._process_pool is not None:
            self._process_pool.cleanup()
            self._process_pool = None

        # Clean up worktree if enabled
        if self._config.isolation_level == IsolationLevel.WORKTREE:
            await self._cleanup_worktree()

        # Clean up artifacts if needed
        # Note: We might want to preserve artifacts for user access
        # self._execution_context.cleanup_artifacts()

        self._is_started = False

    async def run(self, code: str, validate: bool = True) -> Execution:
        """
        Execute Python code in the local sandbox with enhanced error handling.

        Args:
            code: Python code to execute
            validate: Whether to validate code before execution

        Returns:
            An Execution object representing the executed code

        Raises:
            RuntimeError: If the sandbox is not started or execution fails
        """
        if not self._is_started:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        # Route to appropriate execution method based on isolation level
        if self._config.isolation_level == IsolationLevel.PROCESS_POOL:
            return await self._run_in_process_pool(code, validate=validate)
        else:
            return await self._run_in_process(code, validate=validate)

    async def _run_in_process(self, code: str, validate: bool = True) -> Execution:
        """
        Execute code in the current process (default behavior).

        Args:
            code: Python code to execute
            validate: Whether to validate code before execution

        Returns:
            An Execution object representing the executed code
        """
        # Use the enhanced persistent execution context with validation
        import hashlib
        cache_key = hashlib.md5(code.encode()).hexdigest()

        result = self._execution_context.execute_code(
            code,
            cache_key=cache_key,
            validate=validate
        )

        # Create and return execution result with enhanced information
        execution = Execution(
            stdout=result.get('stdout', ''),
            stderr=result.get('stderr', ''),
            return_value=None,  # Will be enhanced in future versions
            exception=Exception(result['error']) if result.get('error') else None,
            artifacts=result.get('artifacts', []),
        )

        # Add validation result to execution if available
        if result.get('validation_result'):
            execution._validation_result = result['validation_result']

        return execution

    async def _run_in_process_pool(self, code: str, validate: bool = True) -> Execution:
        """
        Execute code in an isolated process from the process pool.

        Provides process-level isolation to prevent module pollution between
        executions while keeping resource usage capped.

        Args:
            code: Python code to execute
            validate: Whether to validate code before execution

        Returns:
            An Execution object representing the executed code
        """
        from ..core.process_pool import get_process_pool
        from ..core.code_validator import CodeValidator

        # Validate code if requested
        if validate:
            validator = CodeValidator()
            validation_result = validator.validate_and_format(code)
            if not validation_result.get('valid', True):
                # Extract error message from issues
                issues = validation_result.get('issues', [])
                error_msg = '; '.join(issues) if issues else 'Code validation failed'
                return Execution(
                    stdout='',
                    stderr=error_msg,
                    exception=Exception(error_msg),
                )

        # Get or create process pool
        if self._process_pool is None:
            self._process_pool = get_process_pool(max_workers=self._config.max_workers)

        # Execute in isolated process
        result = self._process_pool.execute_isolated(
            code=code,
            session_id=self._name,
            artifacts_dir=str(self._execution_context.artifacts_dir or '/tmp/sandbox-artifacts'),
            timeout=self._config.timeout,
            memory_limit_mb=self._config.memory_limit_mb,
        )

        # Create and return execution result
        return Execution(
            stdout=result.get('output', ''),
            stderr=result.get('error', ''),
            return_value=None,
            exception=Exception(result['error']) if result.get('error') else None,
            artifacts=result.get('artifacts', []),
        )

    @property
    def artifacts_dir(self) -> Optional[str]:
        """
        Get the artifacts directory path.
        """
        return str(self._execution_context.artifacts_dir) if self._execution_context.artifacts_dir else None

    def list_artifacts(self, format_type: str = 'list', recursive: bool = True) -> Any:
        """
        List all artifacts created during execution with recursive scanning.
        
        Args:
            format_type: Output format ('list', 'json', 'csv', 'detailed')
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            Artifacts in the requested format
        """
        if not self._execution_context.artifacts_dir:
            return [] if format_type == 'list' else self._format_empty_artifacts(format_type)
            
        artifacts_dir = Path(self._execution_context.artifacts_dir)
        if not artifacts_dir.exists():
            return [] if format_type == 'list' else self._format_empty_artifacts(format_type)
        
        # Get artifacts with full details
        artifacts = []
        pattern = "**/*" if recursive else "*"
        
        for file_path in artifacts_dir.glob(pattern):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    artifact_info = {
                        'name': file_path.name,
                        'path': str(file_path.relative_to(artifacts_dir)),
                        'full_path': str(file_path),
                        'size': stat.st_size,
                        'created': stat.st_ctime,
                        'modified': stat.st_mtime,
                        'extension': file_path.suffix.lower(),
                        'type': self._categorize_file(file_path)
                    }
                    artifacts.append(artifact_info)
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")
        
        return self._format_artifacts_output(artifacts, format_type)
    
    def _categorize_file(self, file_path: Path) -> str:
        """Categorize a file based on its extension and path."""
        suffix = file_path.suffix.lower()
        path_str = str(file_path).lower()
        
        # Check for Manim files
        if any(pattern in path_str for pattern in ['manim', 'media', 'videos', 'images']):
            return 'manim'
        
        # Extension-based categorization
        type_mappings = {
            'images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.webp'},
            'videos': {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'},
            'data': {'.csv', '.json', '.xml', '.yaml', '.yml', '.pkl', '.pickle', '.h5', '.hdf5'},
            'code': {'.py', '.js', '.html', '.css', '.sql', '.sh', '.bat'},
            'documents': {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'},
            'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        }
        
        for category, extensions in type_mappings.items():
            if suffix in extensions:
                return category
        
        return 'other'
    
    def _format_empty_artifacts(self, format_type: str) -> Any:
        """Format empty artifacts response."""
        if format_type == 'json':
            return json.dumps([])
        elif format_type == 'csv':
            return 'name,path,size,created,modified,extension,type\n'
        elif format_type == 'detailed':
            return {'total': 0, 'files': [], 'categories': {}}
        else:
            return []
    
    def _format_artifacts_output(self, artifacts: List[Dict], format_type: str) -> Any:
        """Format artifacts output in the requested format."""
        if format_type == 'list':
            return [artifact['path'] for artifact in artifacts]
        
        elif format_type == 'json':
            import json
            return json.dumps(artifacts, indent=2)
        
        elif format_type == 'csv':
            import csv
            import io
            output = io.StringIO()
            if artifacts:
                writer = csv.DictWriter(output, fieldnames=artifacts[0].keys())
                writer.writeheader()
                writer.writerows(artifacts)
            return output.getvalue()
        
        elif format_type == 'detailed':
            # Group by category
            categories = {}
            for artifact in artifacts:
                category = artifact['type']
                if category not in categories:
                    categories[category] = []
                categories[category].append(artifact)
            
            return {
                'total': len(artifacts),
                'files': artifacts,
                'categories': categories,
                'summary': {
                    cat: {'count': len(files), 'total_size': sum(f['size'] for f in files)}
                    for cat, files in categories.items()
                }
            }
        
        else:
            return artifacts

    def cleanup_artifacts(self) -> None:
        """
        Clean up all artifacts.
        """
        self._execution_context.cleanup_artifacts()

    def get_execution_info(self) -> Dict[str, Any]:
        """
        Get information about the execution environment.
        """
        return {
            "python_version": sys.version,
            "executable": sys.executable,
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "project_root": str(self._execution_context.project_root),
            "artifacts_dir": self.artifacts_dir,
            "sys_path": sys.path[:10],  # First 10 entries
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from the execution context.
        """
        return self._execution_context.get_execution_stats()
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history.
        """
        return self._execution_context.get_execution_history(limit=limit)
    
    def clear_cache(self) -> None:
        """
        Clear compilation and execution cache.
        """
        self._execution_context.clear_cache()
    
    def save_session(self) -> None:
        """
        Manually save the current execution session state.
        """
        self._execution_context.save_persistent_state()
    
    @property
    def session_id(self) -> str:
        """
        Get the current session ID.
        """
        return self._execution_context.session_id
    
    def cleanup_session(self) -> None:
        """
        Cleanup the current session.
        """
        self._execution_context.cleanup()
    
    def get_artifact_report(self) -> Dict[str, Any]:
        """
        Get comprehensive artifact report with categorization.
        """
        return self._execution_context.get_artifact_report()
    
    def categorize_artifacts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize artifacts by type with detailed metadata.
        """
        return self._execution_context.categorize_artifacts()
    
    def cleanup_artifacts_by_type(self, artifact_type: str) -> int:
        """
        Clean up artifacts of a specific type.
        
        Args:
            artifact_type: Type of artifacts to clean (e.g., 'images', 'videos', 'plots')
            
        Returns:
            Number of artifacts cleaned up
        """
        if not self._execution_context.artifacts_dir:
            return 0
            
        categorized = self.categorize_artifacts()
        if artifact_type not in categorized:
            return 0
            
        cleaned_count = 0
        for file_info in categorized[artifact_type]:
            try:
                file_path = Path(file_info['full_path'])
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file_info['path']}: {e}")
        
        return cleaned_count
    
    def get_manim_artifacts(self) -> List[Dict[str, Any]]:
        """
        Get all Manim-related artifacts.
        """
        categorized = self.categorize_artifacts()
        return categorized.get('manim', [])
    
    def get_artifact_summary(self) -> str:
        """
        Get a human-readable summary of artifacts.
        """
        report = self.get_artifact_report()
        
        if report['total_artifacts'] == 0:
            return "No artifacts found."
        
        def format_size(bytes_size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.1f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.1f} TB"
        
        lines = [
            f"Total Artifacts: {report['total_artifacts']}",
            f"Total Size: {format_size(report['total_size'])}",
            "",
            "Categories:"
        ]
        
        for category, info in report['categories'].items():
            lines.append(f"  {category}: {info['count']} files ({format_size(info['size'])})")
        
        if report['recent_artifacts']:
            lines.extend([
                "",
                "Recent Artifacts:"
            ])
            for artifact in report['recent_artifacts'][:5]:
                lines.append(f"  {artifact['name']} ({format_size(artifact['size'])})")
        
        return "\n".join(lines)
    
    def start_interactive_repl(self) -> None:
        """Start an enhanced interactive REPL session."""
        from ..core.interactive_repl import EnhancedREPL
        
        repl = EnhancedREPL(self._execution_context)
        repl.start_interactive_session()
    
    def get_code_template(self, template_type: str) -> str:
        """Get code templates for common tasks."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.get_code_template(template_type)
    
    def get_available_templates(self) -> List[str]:
        """Get list of available code templates."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.get_available_templates()
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """Validate code before execution."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.validate_and_format(code)
    
    def get_manim_helper(self):
        """Get Manim helper for animation support."""
        from ..core.manim_support import ManIMHelper
        
        return ManIMHelper(self._execution_context.artifacts_dir)
