"""
Configuration classes for the enhanced Sandbox SDK.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union


class IsolationLevel(Enum):
    """
    Isolation level for sandbox execution.

    Each level provides different guarantees about module isolation and resource usage.
    """

    IN_PROCESS = "in_process"  # Current behavior - shared process, fastest
    PROCESS_POOL = "process_pool"  # Process pool isolation (future), balanced
    WORKTREE = "worktree"  # Git worktree isolation (implemented) - complete filesystem isolation
    CONTAINER = "container"  # Container isolation (delegates to RemoteSandbox)


@dataclass
class SandboxConfig:
    """
    Configuration for sandbox execution.
    """

    # Core settings
    remote: bool = False
    server_url: Optional[str] = None
    namespace: str = "default"
    name: Optional[str] = None
    api_key: Optional[str] = None

    # Resource limits
    memory: int = 512  # MB
    cpus: float = 1.0
    timeout: float = 180.0  # seconds

    # Image settings
    image: Optional[str] = None

    # Environment variables
    env: Dict[str, str] = field(default_factory=dict)

    # Volume mounts for local sandboxes
    mounts: List[str] = field(default_factory=list)

    # Working directory
    working_directory: Optional[str] = None

    # Isolation settings
    isolation_level: IsolationLevel = IsolationLevel.IN_PROCESS
    max_workers: Optional[int] = None  # For process pool
    memory_limit_mb: Optional[int] = None  # Per-process memory limit

    # Worktree isolation settings (used when isolation_level == WORKTREE)
    worktree_base_branch: Optional[str] = None  # None = use current branch
    auto_merge_on_close: bool = False  # Auto-merge worktree on sandbox close
    auto_delete_worktree: bool = True  # Auto-delete worktree after merge/close
    worktree_commit_message: Optional[str] = None  # Custom commit message for merge


@dataclass
class SandboxOptions:
    """
    Builder pattern for creating sandbox configurations.
    """
    
    _config: SandboxConfig = field(default_factory=SandboxConfig)
    
    def remote(self, enabled: bool = True) -> 'SandboxOptions':
        """Enable remote sandbox execution."""
        self._config.remote = enabled
        return self
    
    def server_url(self, url: str) -> 'SandboxOptions':
        """Set the server URL for remote execution."""
        self._config.server_url = url
        return self
    
    def namespace(self, namespace: str) -> 'SandboxOptions':
        """Set the namespace for the sandbox."""
        self._config.namespace = namespace
        return self
    
    def name(self, name: str) -> 'SandboxOptions':
        """Set the name for the sandbox."""
        self._config.name = name
        return self
    
    def api_key(self, key: str) -> 'SandboxOptions':
        """Set the API key for authentication."""
        self._config.api_key = key
        return self
    
    def memory(self, memory_mb: int) -> 'SandboxOptions':
        """Set the memory limit in MB."""
        self._config.memory = memory_mb
        return self
    
    def cpus(self, cpu_count: float) -> 'SandboxOptions':
        """Set the CPU limit."""
        self._config.cpus = cpu_count
        return self
    
    def timeout(self, timeout_seconds: float) -> 'SandboxOptions':
        """Set the timeout for sandbox operations."""
        self._config.timeout = timeout_seconds
        return self
    
    def image(self, image_name: str) -> 'SandboxOptions':
        """Set the Docker image to use."""
        self._config.image = image_name
        return self
    
    def env(self, key: str, value: str) -> 'SandboxOptions':
        """Set an environment variable."""
        self._config.env[key] = value
        return self
    
    def envs(self, env_vars: Dict[str, str]) -> 'SandboxOptions':
        """Set multiple environment variables."""
        self._config.env.update(env_vars)
        return self
    
    def mount(self, host_path: str, container_path: str) -> 'SandboxOptions':
        """Add a volume mount for local sandboxes."""
        self._config.mounts.append(f"{host_path}:{container_path}")
        return self
    
    def working_directory(self, path: str) -> 'SandboxOptions':
        """Set the working directory."""
        self._config.working_directory = path
        return self

    def isolation_level(self, level: IsolationLevel) -> 'SandboxOptions':
        """Set the isolation level for sandbox execution."""
        self._config.isolation_level = level
        return self

    def max_workers(self, count: int) -> 'SandboxOptions':
        """Set the maximum number of workers for process pool."""
        self._config.max_workers = count
        return self

    def memory_limit(self, limit_mb: int) -> 'SandboxOptions':
        """Set the per-process memory limit in MB."""
        self._config.memory_limit_mb = limit_mb
        return self

    def worktree(
        self,
        base_branch: Optional[str] = None,
        auto_merge: bool = False,
        auto_delete: bool = True,
        commit_message: Optional[str] = None,
    ) -> 'SandboxOptions':
        """Enable worktree isolation with options."""
        self._config.isolation_level = IsolationLevel.WORKTREE
        self._config.worktree_base_branch = base_branch
        self._config.auto_merge_on_close = auto_merge
        self._config.auto_delete_worktree = auto_delete
        self._config.worktree_commit_message = commit_message
        return self

    def build(self) -> SandboxConfig:
        """Build the final configuration."""
        return self._config
    
    @classmethod
    def builder(cls) -> 'SandboxOptions':
        """Create a new SandboxOptions builder."""
        return cls()
