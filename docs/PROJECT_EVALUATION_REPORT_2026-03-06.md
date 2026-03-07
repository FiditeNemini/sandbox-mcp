# Project Evaluation Report

Date: 2026-03-06
Project: `sandbox-mcp`
Assessment method: `leindex` CLI indexing/search/phase analysis plus targeted runtime validation

## Executive Summary

The project has a promising core idea and a meaningful amount of functionality already implemented: MCP server support, artifact capture, persistent execution context, resource tracking, and an SDK surface for local and remote sandbox use. LeIndex indexed the codebase cleanly and surfaced a reasonably rich graph:

- 35 source files
- 379 signatures
- 764 PDG nodes
- 2857 PDG edges
- 10 entry points
- 12 documentation files

At the same time, the repository is not in a release-ready state. The main risks are not subtle:

1. A core source file has a syntax error, which means part of the execution pipeline cannot compile.
2. The package import path is broken under the declared dependency set.
3. Test infrastructure is configured but no tests exist.
4. Documentation and metadata materially diverge from the actual package state.
5. The codebase is carrying significant architectural duplication and coupling, especially around the stdio server and execution context.

Overall assessment: strong prototype / experimental platform, but not yet at a stable production-quality SDK/server release bar.

## LeIndex Findings

### Index snapshot

- Indexing completed successfully in 145ms.
- LeIndex found 35 source files with 0 parse failures during indexing.
- Phase analysis reported 10 entry points and 10 hotspot files.
- Documentation analysis found 12 docs files, 645 headings, and 3 TODOs.

### Structural signals

- The repository has multiple entry surfaces: [`run_sandbox.py`](/home/scooter/Documents/Product/sandbox-mcp/run_sandbox.py), [`main.py`](/home/scooter/Documents/Product/sandbox-mcp/main.py), [`playground.py`](/home/scooter/Documents/Product/sandbox-mcp/playground.py), [`src/sandbox/mcp_sandbox_server.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/mcp_sandbox_server.py), [`src/sandbox/mcp_sandbox_server_stdio.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/mcp_sandbox_server_stdio.py), and SDK entry points.
- LeIndex phase analysis reported 322 external import edges and 115 unresolved modules. Some of that is expected for stdlib/external libraries, but in this repo it also lines up with genuine dependency and packaging problems.
- The strongest semantic hotspots cluster around:
  - stdio MCP server
  - execution context
  - security/resource management
  - local sandbox SDK

## Confirmed Issues

### Critical

#### 1. `code_validator.py` contains a hard syntax error

Evidence:

- [`src/sandbox/core/code_validator.py#L74`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/code_validator.py#L74) contains a literal `\n` embedded in executable Python:
  - `return {'valid': True, 'issues': []}\n        except SyntaxError as e:`
- `uv run python -m compileall src` fails on this file.

Impact:

- Validation logic is not trustworthy.
- Any execution path importing this module will fail.
- This blocks confidence in one of the project’s core safety layers.

Recommended remediation:

- Fix the syntax error immediately.
- Add a minimal smoke test that imports `CodeValidator` and exercises `validate_and_format()`.

#### 2. Package import fails with declared dependencies

Evidence:

- `uv run python -c "import sandbox"` fails with `ModuleNotFoundError: No module named 'aiohttp'`.
- [`src/sandbox/sdk/base_sandbox.py#L12`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/base_sandbox.py#L12) imports `aiohttp`.
- [`src/sandbox/sdk/command.py#L9`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/command.py#L9), [`src/sandbox/sdk/remote_sandbox.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/remote_sandbox.py), and [`src/sandbox/sdk/node_sandbox.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/node_sandbox.py) also depend on it.
- [`pyproject.toml#L7`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L7) to [`pyproject.toml#L21`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L21) does not declare `aiohttp`.

Impact:

- The published package contract is broken.
- `import sandbox` is not safe in a clean environment.
- Consumers hit failures before using any feature.

Recommended remediation:

- Add missing direct dependencies to `pyproject.toml`.
- Make optional features genuinely optional instead of imported eagerly.

#### 3. Eager package imports make optional or broken submodules fatal

Evidence:

- [`src/sandbox/__init__.py#L14`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/__init__.py#L14) to [`src/sandbox/__init__.py#L26`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/__init__.py#L26) imports server modules, SDK modules, and concrete sandbox implementations on package import.
- [`src/sandbox/sdk/__init__.py#L10`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/__init__.py#L10) to [`src/sandbox/sdk/__init__.py#L19`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/__init__.py#L19) eagerly imports all SDK submodules.

Impact:

- A missing optional dependency breaks the entire package import.
- Import-time side effects make the library harder to embed, test, and package.

Recommended remediation:

- Convert `__init__.py` exports to lazy imports or narrow them to stable primitives.
- Separate optional integrations behind explicit import paths or extras.

### High

#### 4. There is no real test suite

Evidence:

- [`pyproject.toml#L24`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L24) to [`pyproject.toml#L29`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L29) configures pytest.
- `uv run pytest -q` collected `0 items`.
- No `tests/` directory was found.

Impact:

- Regressions are currently undetectable except through manual exploration.
- Refactoring the large server files will be risky until a safety net exists.

Recommended remediation:

- Add smoke tests first:
  - package import
  - MCP server startup
  - local execution happy path
  - artifact capture
  - security filter behavior
- Then add targeted regression tests for execution context and web-app launch paths.

#### 5. Metadata and docs are materially inconsistent

Evidence:

- [`pyproject.toml#L7`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L7) declares version `0.1.0`.
- [`src/sandbox/__init__.py#L9`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/__init__.py#L9) and [`src/sandbox/sdk/__init__.py#L8`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/__init__.py#L8) declare `0.3.0`.
- [`README.md#L5`](/home/scooter/Documents/Product/sandbox-mcp/README.md#L5) and [`README.md#L78`](/home/scooter/Documents/Product/sandbox-mcp/README.md#L78) advertise Python `3.9+`.
- [`pyproject.toml#L10`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml#L10) requires Python `>=3.11`.
- [`docs/FAQ_AND_LIMITATIONS.md#L12`](/home/scooter/Documents/Product/sandbox-mcp/docs/FAQ_AND_LIMITATIONS.md#L12) describes a fixed environment path that does not match this repo layout.

Impact:

- Users cannot tell what version they are installing or what runtime is supported.
- Documentation confidence drops quickly when basic setup facts disagree.

Recommended remediation:

- Define a single source of truth for version and Python support.
- Sweep README/docs for claims about installed packages, paths, and capabilities.

#### 6. Claimed web-app features are not backed by declared dependencies

Evidence:

- README and docs repeatedly advertise Flask and Streamlit support, for example:
  - [`README.md#L59`](/home/scooter/Documents/Product/sandbox-mcp/README.md#L59)
  - [`docs/FAQ_AND_LIMITATIONS.md#L84`](/home/scooter/Documents/Product/sandbox-mcp/docs/FAQ_AND_LIMITATIONS.md#L84)
- `uv run python -c "import flask, streamlit, pandas"` fails because `flask` is not installed.
- [`pyproject.toml`](/home/scooter/Documents/Product/sandbox-mcp/pyproject.toml) does not declare `flask`, `streamlit`, or `pandas`.

Impact:

- Documented features cannot be assumed to work in a fresh install.
- This creates user-facing breakage in demo-heavy flows.

Recommended remediation:

- Decide which of these are core dependencies, optional extras, or examples-only integrations.
- Align docs and packaging accordingly.

#### 7. The stdio server is oversized and likely carrying too many responsibilities

Evidence:

- [`src/sandbox/mcp_sandbox_server_stdio.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/mcp_sandbox_server_stdio.py) is 2727 lines.
- It contains execution context logic, artifact backup/rollback, web-app export, package installation helpers, REPL helpers, guidance text, and MCP tool implementations.
- LeIndex ranked it as the dominant hotspot for entry points and capability-related queries.

Impact:

- High change risk.
- Harder code review, testing, and reasoning.
- Strong chance of feature drift between server variants.

Recommended remediation:

- Split by concern:
  - execution/session services
  - artifact services
  - web export services
  - MCP tool registration
  - REPL UX/help text

### Medium

#### 8. Architectural duplication exists around execution context and server behavior

Evidence:

- There is an `ExecutionContext` inside [`src/sandbox/mcp_sandbox_server.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/mcp_sandbox_server.py).
- There is another `ExecutionContext` inside [`src/sandbox/mcp_sandbox_server_stdio.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/mcp_sandbox_server_stdio.py).
- There is also [`src/sandbox/core/execution_context.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/execution_context.py) with `PersistentExecutionContext`.
- [`src/sandbox/sdk/local_sandbox.py#L18`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/local_sandbox.py#L18) imports `ExecutionContext` helpers from the stdio server module, tightly coupling SDK code to server implementation details.

Impact:

- Bugs are more likely to be fixed in one place and missed in another.
- The SDK depends on the server module shape, which is backwards from a clean layering model.

Recommended remediation:

- Move shared execution/artifact behavior into `src/sandbox/core/`.
- Make both MCP servers and the SDK depend on core services, not each other.

#### 9. “Sandbox” security is currently more policy signaling than enforced isolation

Evidence:

- [`src/sandbox/core/security.py#L45`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/security.py#L45) uses regex- and substring-based filtering.
- [`src/sandbox/sdk/command.py#L117`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/command.py#L117) to [`src/sandbox/sdk/command.py#L157`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/sdk/command.py#L157) executes local commands with `subprocess.run(...)` after a small blacklist check.
- Docs claim restrictions such as “No internet access” and strong isolation in [`docs/FAQ_AND_LIMITATIONS.md#L173`](/home/scooter/Documents/Product/sandbox-mcp/docs/FAQ_AND_LIMITATIONS.md#L173), but there is no OS-level network or filesystem sandboxing demonstrated in these paths.

Impact:

- Security claims may overstate the actual protection level.
- Consumers may use the project in higher-trust contexts than it currently supports.

Recommended remediation:

- Reframe the project as a guarded execution environment unless true isolation is implemented.
- If strong isolation is required, add container/microVM/process sandboxing and enforce network/filesystem controls below the Python layer.

#### 10. Persistent state uses pickle fallback, which is risky if storage is not fully trusted

Evidence:

- [`src/sandbox/core/execution_context.py#L209`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/execution_context.py#L209) to [`src/sandbox/core/execution_context.py#L214`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/execution_context.py#L214) loads pickled values.
- [`src/sandbox/core/execution_context.py#L239`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/execution_context.py#L239) to [`src/sandbox/core/execution_context.py#L242`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/execution_context.py#L242) stores pickle when JSON serialization fails.

Impact:

- If session storage is tampered with, unpickling can become a code execution vector.

Recommended remediation:

- Prefer JSON-only persistence or explicit serializers for supported value types.
- If pickle remains, document the trust boundary clearly.

## Strengths

- The repo has a coherent product direction: execution sandbox + MCP server + artifact workflows.
- Resource and lifecycle management are at least being considered, especially in [`src/sandbox/core/resource_manager.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/resource_manager.py).
- There is evidence of thoughtful UX ambition: artifact handling, REPL commands, web app launching/export, and Manim support.
- LeIndex indexed the codebase cleanly and found a non-trivial structure, which suggests the code is not random sprawl even though some parts need consolidation.

## Areas Requiring Remediation

### Immediate

1. Fix syntax/runtime blockers.
2. Make `import sandbox` succeed in a clean environment.
3. Add a minimal smoke test suite.
4. Reconcile version/dependency/runtime documentation.

### Short term

1. Collapse duplicate execution context and server logic into shared core modules.
2. Reduce import-time side effects and eager imports.
3. Decide the supported feature matrix:
   - core package
   - optional web extras
   - optional SDK/remote extras

### Medium term

1. Replace blacklist-style command filtering with stronger execution isolation.
2. Introduce architecture boundaries between:
   - SDK
   - execution core
   - MCP adapters
   - REPL/demo surfaces

## Improvement And Optimization Opportunities

### Product and packaging

- Introduce dependency extras such as `web`, `sdk-remote`, and `dev`.
- Publish a supported feature matrix in the README.
- Stop exposing unstable internals from package top-level imports.

### Codebase design

- Split the stdio server into smaller service modules.
- Move shared monkey-patching and artifact behavior out of server files and into reusable core utilities.
- Treat `src/sandbox/core/` as the real domain layer and make adapters thin.

### Quality engineering

- Add CI steps for:
  - `python -m compileall src`
  - package import smoke test
  - `pytest`
  - docs consistency checks for version/Python support
- Add a “golden path” end-to-end test that exercises local execution plus artifact generation.

### Performance and maintainability

- Reduce import-time work and global initialization.
- Avoid large monolithic modules that mix runtime logic, help text, export templates, and tool wiring.
- Track startup time and memory usage for server initialization after refactoring.

## Recommended Priority Plan

### Priority 0

- Fix [`src/sandbox/core/code_validator.py`](/home/scooter/Documents/Product/sandbox-mcp/src/sandbox/core/code_validator.py).
- Add missing direct dependencies or gate optional imports.
- Make `import sandbox` pass.

### Priority 1

- Add smoke tests for import/startup/execution.
- Align `pyproject`, package version constants, and README/docs.

### Priority 2

- Refactor shared execution/context logic out of the MCP server files.
- Reduce top-level import coupling in package init modules.

### Priority 3

- Revisit security positioning and implementation so the project’s claims match the actual isolation model.

## Validation Notes

Commands used during assessment included:

- `leindex index /home/scooter/Documents/Product/sandbox-mcp --progress --force`
- `leindex phase --all -p /home/scooter/Documents/Product/sandbox-mcp --mode verbose --include-docs --docs-mode markdown`
- targeted `leindex search` queries for entry points, tests, security, duplication, and metadata drift
- `uv run pytest -q`
- `uv run python -m compileall src`
- `uv run python -c "import sandbox"`

## Final Assessment

This repository already contains enough functionality to be valuable, but it currently behaves like a feature-rich prototype rather than a hardened SDK/server package. The path to a much stronger state is straightforward: fix the hard blockers, establish a small but real test harness, align the package contract with the docs, and then refactor the large duplicated server code into shared core services.
