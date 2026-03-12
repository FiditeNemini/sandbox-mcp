"""
Core sandbox functionality with enhanced execution context and performance optimizations.
"""

from .execution_context import PersistentExecutionContext
from .execution_services import ExecutionContext, ExecutionContextService, get_execution_service
from .artifact_services import ArtifactService, get_artifact_service
from .patching import PatchManager, get_patch_manager
from .process_pool import SandboxProcessPool, get_process_pool, cleanup_global_process_pool
from .worktree_manager import WorktreeManager, find_git_repo
from .worktree_isolation import (
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

__all__ = [
    "PersistentExecutionContext",
    "ExecutionContext",
    "ExecutionContextService",
    "get_execution_service",
    "ArtifactService",
    "get_artifact_service",
    "PatchManager",
    "get_patch_manager",
    "SandboxProcessPool",
    "get_process_pool",
    "cleanup_global_process_pool",
    "WorktreeManager",
    "find_git_repo",
    "WorktreeIsolationManager",
    "WorktreeInfo",
    "WorktreeStatus",
    "get_worktree_manager",
    "GitError",
    "GitNotFoundError",
    "NotARepositoryError",
    "WorktreeCreationError",
    "MergeConflictError",
]
