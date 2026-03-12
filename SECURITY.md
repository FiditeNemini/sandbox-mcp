# Security Model and Threat Model

## Overview

Sandbox MCP Server is designed for **single-user developer scenarios** with isolated execution contexts for LLM code generation. This document clarifies what security properties it provides and what it does NOT provide.

## Intended Use Cases

### ✅ Designed For
- **Single-user development**: One developer using the sandbox locally
- **LLM code generation**: Isolated contexts for AI-generated code
- **Artifact management**: Capture and organize execution outputs
- **Development workflows**: Experimentation, prototyping, learning

### ❌ NOT Designed For
- **Multi-tenant isolation**: Multiple untrusted users
- **Production security**: Running untrusted production code
- **Malicious code isolation**: Preventing deliberate attacks
- **Process-level security**: Complete OS-level isolation

## Threat Model

### Single Developer + Single LLM
**Status**: ✅ SECURE

The sandbox provides strong isolation between execution contexts:
- Separate `execution_globals` per session
- Isolated `artifacts_dir` per session
- Path traversal prevention
- Symlink exfiltration prevention
- Thread-safe session management

### Single Developer + Multiple LLMs (Same Sandbox Instance)
**Status**: ⚠️ PARTIAL ISOLATION (Level 1: In-Process)

**What's Isolated:**
- Execution globals (variables, functions)
- Artifacts directories
- Session state

**What's Shared:**
- Imported modules (sys.modules)
- Process-wide state (sys.path, os.environ)
- File system (sessions can see each other's files if they know paths)

**Recommendation**: For multiple LLMs, use **Level 2: Process Pool isolation** for module isolation.

**Status with Process Pool**: ✅ SECURE (Level 2: Process Pool)

When using `IsolationLevel.PROCESS_POOL`:
- Each LLM execution runs in a separate process
- Module pollution is completely prevented
- Memory limits prevent resource exhaustion
- Timeouts prevent runaway processes

**What's Isolated (Process Pool):**
- Complete process space (sys.modules, globals, etc.)
- Memory (enforced per process)
- CPU time (timeout enforcement)

**What's Shared (Process Pool):**
- File system (can still see files if path known)
- Worker pool (limited by max_workers)

**Recommendation**: For complete isolation, use **Level 3: Worktree** or **Level 4: Container**.

### Multiple Sandbox Instances (Same Machine)
**Status**: ✅ SECURE with caveats

Each instance is fully isolated if:
- Different working directories
- Different port numbers (for HTTP transport)
- Separate Python processes

**Resource Management**: Each instance consumes:
- Memory: ~50-100MB base + execution overhead
- CPU: Minimal when idle
- Disk: Artifacts + session state

**Recommendation**: Use `max_instances` config to limit concurrent instances.

### Multi-Instance Resource Management

When running multiple sandbox instances simultaneously:

**Memory Considerations:**
- Base memory per instance: 50-100MB
- With process pool: Each worker adds ~20-50MB
- Calculation: `total_memory = instances × (base + max_workers × worker_memory)`

**Example:**
```
4 instances × (100MB + 4 workers × 30MB) = 640MB
```

**CPU Considerations:**
- Idle instances use minimal CPU
- Active executions use 1 CPU core per worker
- Hyper-threading can provide ~1.5x effective cores

**Configuration Example:**
```python
# For a machine with 8GB RAM and 4 CPU cores
MAX_INSTANCES = 4
MAX_WORKERS_PER_INSTANCE = 2  # Total: 4×2 = 8 workers
MEMORY_LIMIT_MB = 256         # Per-process limit
```

**Monitoring:**
- Monitor `/proc/meminfo` for memory pressure
- Use `ulimit -u` to limit total processes
- Consider cgroups for production deployments

### Network Security

**stdio transport**: Secure - no network exposure
**HTTP transport**: Should use authentication in production

## Isolation Levels

### Comparison Table

| Isolation Level | Module Isolation | Filesystem Isolation | Resource Limits | Performance | Use Case |
|----------------|------------------|---------------------|-----------------|-------------|----------|
| **Level 1: In-Process** | ❌ Shared modules | ❌ Shared filesystem | ❌ No limits | ⭐⭐⭐⭐⭐ Fastest | Single LLM, trusted code |
| **Level 2: Process Pool** | ✅ Isolated modules | ❌ Shared filesystem | ✅ Memory + timeout | ⭐⭐⭐⭐ Fast | Multiple LLMs |
| **Level 3: Worktree** | ❌ Shared modules | ✅ Isolated filesystem | ❌ No limits | ⭐⭐⭐ Moderate | Parallel development |
| **Level 4: Container** | ✅ Isolated modules | ✅ Isolated filesystem | ✅ Full quotas | ⭐⭐ Slower | Untrusted code |

### Level 1: In-Process Isolation (Current)
- Separate execution contexts
- Shared process space
- **Use case**: Single developer + trusted LLM

### Level 2: Process Pool Isolation (Implemented)
- Resource-efficient process pool
- Shared filesystem
- Module-level isolation (no module pollution)
- Configurable memory and timeout limits per process
- **Use case**: Single developer + multiple LLMs

**Usage:**
```python
from sandbox.sdk import LocalSandbox, SandboxConfig, IsolationLevel

config = SandboxConfig(
    isolation_level=IsolationLevel.PROCESS_POOL,
    max_workers=4,           # Max concurrent processes
    memory_limit_mb=256,     # Per-process memory limit
    timeout=30.0             # Execution timeout
)

async with LocalSandbox.create(name="my-session", config=config) as sandbox:
    result = await sandbox.run("print('Isolated execution')")
```

**Security Properties:**
- ✅ Module pollution prevented (each process has isolated `sys.modules`)
- ✅ Memory limits enforced per process (platform-dependent)
- ✅ Timeout enforcement kills runaway processes
- ✅ Worker pool caps resource usage

### Level 3: Worktree Isolation (Implemented)
- Git worktree per session
- Complete filesystem isolation
- Optional merge capabilities
- **Use case**: Parallel development workflows

**Usage:**
```python
from sandbox.sdk import WorktreeSandbox

async with WorktreeSandbox.create(
    name="my-session",
    base_branch="main",
    auto_merge=True,
) as sandbox:
    result = await sandbox.run("print('Isolated execution')")
    # Changes can be merged back on exit
```

### Level 4: Container Isolation (External)
- Use RemoteSandbox with microVMs
- Full OS-level isolation
- **Use case**: Untrusted code, production use

**Usage:**
```python
from sandbox.sdk import RemoteSandbox

async with RemoteSandbox.create(
    name="my-session",
    server_url="http://microsandbox:5555",
) as sandbox:
    result = await sandbox.run("print('Fully isolated execution')")
```

## Security Considerations by Isolation Level

### Level 1: In-Process Isolation

**Threats:**
- Module pollution: `import sys; sys.hook = lambda: "malicious"`
- Filesystem access: `open('/etc/passwd').read()`
- Resource exhaustion: `x = "a" * 10_000_000_000`
- Timing side-channels: Detect other executions via timing

**Mitigations:**
- ✅ Path traversal protection (CRIT-1, CRIT-2)
- ✅ Symlink exfiltration prevention (CRIT-3)
- ✅ Session isolation (CRIT-4)
- ✅ Command filtering for shell access

**When to Use:**
- Single LLM scenarios
- Trusted code
- Development environments

### Level 2: Process Pool Isolation

**Threats Mitigated:**
- ✅ Module pollution prevented (separate process)
- ✅ Resource exhaustion (memory limits per process)
- ✅ Timing attacks (separate processes)

**Remaining Threats:**
- ⚠️ Filesystem access (shared filesystem)
- ⚠️ Inter-process communication (pipes, sockets)
- ⚠️ Parent process compromise

**Mitigations:**
- Memory limit enforcement via `resource.RLIMIT_AS` (Unix)
- Timeout enforcement via `concurrent.futures`
- Worker pool limits resource usage

**When to Use:**
- Multiple LLMs
- Untrusted module imports
- Resource-constrained environments

### Level 3: Worktree Isolation

**Threats Mitigated:**
- ✅ Filesystem isolation (separate git worktree)
- ✅ Code separation (different branches)
- ✅ Merge review (changes can be inspected)

**Remaining Threats:**
- ⚠️ Module pollution (still in-process)
- ⚠️ Resource exhaustion (no limits)
- ⚠️ Git repository compromise

**Mitigations:**
- Separate working directories per session
- Optional auto-merge with review
- Worktree cleanup on session end

**When to Use:**
- Parallel development workflows
- Testing multiple branches simultaneously
- Filesystem isolation needed

### Level 4: Container Isolation

**Threats Mitigated:**
- ✅ Complete OS-level isolation
- ✅ Network isolation
- ✅ Resource quotas (CPU, memory, disk)
- ✅ Filesystem isolation

**Remaining Threats:**
- ⚠️ Container escape vulnerabilities
- ⚠️ Host compromise affects all containers
- ⚠️ Shared kernel exploits

**Mitigations:**
- Use microVMs (Firecracker) instead of containers
- Network policies restrict egress
- Resource quotas via cgroups

**When to Use:**
- Untrusted code execution
- Production environments
- Multi-tenant scenarios

## Resource Management

### Current Capabilities
- Thread-safe session management
- Artifact cleanup
- Session timeouts
- Memory monitoring
- Git worktree isolation (Level 3)
- Merge capabilities for worktree changes
- **Process pool with resource limits (Level 2)** ✅ NEW
- Configurable worker limits and memory quotas ✅ NEW

### Planned Capabilities
- Concurrent instance limits
- CPU quotas
- Automatic garbage collection
- Network isolation for process pool workers

## Security Properties

### What We Protect Against

✅ **Path Traversal** (CRIT-1, CRIT-2)
- Session ID validation
- Backup name sanitization
- is_relative_to() boundary checks

✅ **Symlink Exfiltration** (CRIT-3)
- Symlinks skipped in artifact scanning
- Resolved path validation

✅ **Cross-Session Leakage** (CRIT-4)
- Thread-local storage for artifacts_dir
- Session-specific execution globals

✅ **Path Validation Bypass** (CRIT-5)
- is_relative_to() prevents prefix attacks

✅ **Transport Divergence** (CRIT-6)
- Identical security posture across transports

### What We Do NOT Protect Against

❌ **Module Pollution** (Level 1: In-Process)
- sys/os module modifications persist
- Imported modules are shared
- **Mitigation**: Use Level 2 (Process Pool) isolation ✅

❌ **Filesystem Access** (Levels 1-2: In-Process, Process Pool)
- Sessions share same filesystem
- Can access files if path known
- **Mitigation**: Use Level 3 (Worktree) or Level 4 (Container) isolation

❌ **Resource Exhaustion** (Level 1: In-Process)
- No CPU/memory limits
- Can create large objects
- **Mitigation**: Use Level 2 (Process Pool) isolation ✅

❌ **Timing Attacks** (Level 1: In-Process)
- Shared process reveals timing
- **Mitigation**: Use Level 2 (Process Pool) isolation ✅

## Security Recommendations

### For Development Use
1. ✅ Use as-is for single LLM scenarios
2. ✅ Trust your LLM (it's your assistant)
3. ✅ Review generated code before execution
4. ✅ Use stdio transport for local development

### For Multi-LLM Scenarios
1. ⚠️ Use separate sandbox instances
2. ⚠️ Configure different working directories
3. ⚠️ Monitor resource usage
4. ⚠️ Implement session cleanup

### For Production Use
1. ❌ Do NOT use directly in production
2. ✅ Use RemoteSandbox with containers
3. ✅ Implement authentication
4. ✅ Add resource quotas
5. ✅ Use network isolation

## Reporting Security Issues

If you discover a security vulnerability, please report it privately via GitHub Security Advisories.

## Security Audits

- **2026-03-12**: TZAR review completed
- **Status**: All critical vulnerabilities fixed
- **Report**: `maestro/tracks/quality-remediation_20260306/TZAR_REVIEW_VERIFICATION.md`
