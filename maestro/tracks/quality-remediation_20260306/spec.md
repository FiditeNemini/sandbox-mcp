# Specification - Sandbox MCP Complete Remediation

**Track Type:** Quality Remediation / Refactor
**Date:** 2026-03-06
**Based on:** PROJECT_EVALUATION_REPORT_2026-03-06.md

---

## Overview

This track addresses all identified issues in the Sandbox MCP Server codebase to bring it from "feature-rich prototype" to "stable production-quality SDK/server release." The remediation is organized by architectural concerns rather than priority levels, with a TDD approach that grows test coverage alongside fixes.

**Current State Assessment:**
- 35 source files, 379 signatures indexed
- Critical syntax error blocking validation layer
- Broken package imports due to missing/undeclared dependencies
- Zero test coverage (0 items collected)
- Version inconsistencies across 4+ files
- Oversized stdio server (2727 lines) with mixed responsibilities

---

## Functional Requirements

### 1. Dependency & Packaging (Fix Import Failures)

**FR-1.1:** Add missing direct dependencies to `pyproject.toml`
- Add `aiohttp` (required by base_sandbox.py, command.py, remote_sandbox.py, node_sandbox.py)
- Add or properly gate Flask/Streamlit as optional extras
- Verify `import sandbox` succeeds in clean environment

**FR-1.2:** Implement dependency extras structure
- Create `[project.optional-dependencies]` groups: `web`, `sdk-remote`, `dev`
- Move optional imports behind lazy loading or explicit import paths
- Ensure core package works without optional dependencies

**FR-1.3:** Fix version inconsistencies
- Single source of truth for version (pyproject.toml)
- Update `src/sandbox/__init__.py` and `src/sandbox/sdk/__init__.py` to read from package
- Align README/docs with declared Python version (>=3.11)

### 2. Critical Syntax & Runtime Errors

**FR-2.1:** Fix `code_validator.py` syntax error
- Remove literal `\n` at line 74 in `return {'valid': True, 'issues': []}\n        except SyntaxError as e:`
- Add smoke test importing CodeValidator and exercising validate_and_format()
- Verify `uv run python -m compileall src` passes

**FR-2.2:** Reduce eager import coupling
- Refactor `src/sandbox/__init__.py` to avoid importing server modules at package level
- Refactor `src/sandbox/sdk/__init__.py` to avoid eager submodule imports
- Move to lazy imports or narrow stable primitives

### 3. Test Infrastructure

**FR-3.1:** Create `tests/` directory structure
- Unit tests directory
- Integration tests directory
- Fixtures directory

**FR-3.2:** Implement smoke tests (TDD - write first, then implement)
- Package import smoke test
- MCP server startup smoke test
- Local execution happy path test
- Artifact capture test
- Security filter behavior test

**FR-3.3:** Add regression tests
- Execution context state persistence
- Web-app launch paths
- Command execution security filtering

### 4. Architectural Refactoring (Group by Concern)

**FR-4.1:** Extract shared core services
- Move duplicate `ExecutionContext` from both MCP servers into `src/sandbox/core/`
- Create shared execution/session services in core
- Create shared artifact services in core
- Make MCP servers and SDK depend on core, not each other

**FR-4.2:** Split stdio server by concern
- Execution/session service module
- Artifact service module
- Web export service module
- MCP tool registration module
- REPL UX/help text module

**FR-4.3:** Move monkey-patching to core utilities
- Extract matplotlib/PIL patching from server files
- Create reusable core utilities for artifact capture

### 5. Security Improvements

**FR-5.1:** Document security positioning accurately
- Update docs to reflect "guarded execution environment" not "strong isolation"
- Remove or qualify claims about "no internet access"

**FR-5.2:** Address pickle security concern
- Prefer JSON-only persistence for session state
- If pickle remains, document trust boundary clearly
- Consider explicit serializers for supported value types

**FR-5.3:** Strengthen command filtering (optional, Priority 3)
- Replace blacklist-style filtering with stronger execution isolation
- Document current limitations of regex/substring filtering

### 6. CI/CD Infrastructure

**FR-6.1:** Add CI pipeline steps
- `python -m compileall src` check
- Package import smoke test
- `pytest` run
- Docs consistency checks for version/Python support

**FR-6.2:** Add golden path end-to-end test
- Exercise local execution + artifact generation
- Verify MCP server responds to tools correctly

---

## Non-Functional Requirements

**NFR-1:** Performance
- Track startup time and memory usage before/after refactoring
- Reduce import-time work and global initialization

**NFR-2:** Code Quality
- No module should exceed 500 lines (down from 2727 in stdio server)
- All new code follows TDD with 90%+ coverage goal

**NFR-3:** Maintainability
- Clear architecture boundaries between SDK, execution core, MCP adapters, REPL surfaces
- Reduce import coupling between modules

---

## Acceptance Criteria

**AC-1:** `uv run python -c "import sandbox"` succeeds without errors
**AC-2:** `uv run pytest` collects and passes all tests
**AC-3:** `uv run python -m compileall src` completes without errors
**AC-4:** Version is consistent across pyproject.toml, __init__.py, README.md
**AC-5:** stdio server split into <5 modules, each <500 lines
**AC-6:** No duplicate ExecutionContext classes - single source in core/
**AC-7:** Documentation accurately describes installed features
**AC-8:** CI pipeline passes all checks

---

## Out of Scope

- Container/microVM-level isolation (deemed Priority 3+, may be separate track)
- New feature development (this is remediation only)
- Breaking API changes to SDK surface (unless required for fixes)

---

## Dependencies

- LeIndex for code analysis validation
- Existing pyproject.toml for base dependency set
- Evaluation report as issue reference

---

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| pytest collected items | 0 | 15+ |
| compileall errors | 1+ | 0 |
| import sandbox errors | Yes | No |
| stdio server lines | 2727 | <500/module |
| version inconsistencies | 4+ | 0 |
