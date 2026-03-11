"""
Validation and sanitization utilities for web export service.

This module provides:
- Input validation (code, export names)
- Name sanitization for security
- Disk space checking for DoS prevention

Security Features:
- Path traversal prevention via export name sanitization
- Docker image name sanitization
- Disk space validation to prevent DoS attacks
"""

from __future__ import annotations

import os
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Tuple, TypedDict

import logging

logger = logging.getLogger(__name__)

# Constants
MAX_CODE_SIZE = 10 * 1024 * 1024  # 10 MB max code size
MAX_EXPORT_NAME_LENGTH = 100
DOCKER_IMAGE_NAME_MAX_LENGTH = 128

# Disk space constants
MIN_FREE_SPACE_BYTES = 100 * 1024 * 1024  # 100 MB minimum free space
MAX_EXPORT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB max per export (including overhead)
DISK_USAGE_WARNING_PERCENT = 90  # Warn when disk usage exceeds this


class ExportResult(TypedDict, total=False):
    """Type-safe export result dictionary."""
    success: bool
    export_name: str
    export_dir: str
    files_created: list[str]
    docker_image: str | None
    error: str | None
    status: str
    message: str
    exports: list[dict[str, object]]
    total_exports: int
    export_info: dict[str, object]
    docker_image_removed: bool
    image_name: str
    build_output: str
    build_error: str
    estimated_size: int


def validate_code(code: str) -> None:
    """
    Validate code input.

    Args:
        code: The code to validate.

    Raises:
        ValueError: If code is invalid.
    """
    if not code or not isinstance(code, str):
        raise ValueError("Code must be a non-empty string")

    if len(code) > MAX_CODE_SIZE:
        raise ValueError(
            f"Code exceeds maximum size of {MAX_CODE_SIZE / (1024 * 1024):.0f} MB"
        )

    # Check for null bytes
    if '\x00' in code:
        raise ValueError("Code cannot contain null bytes")

    # Check for whitespace-only code
    if not code.strip():
        raise ValueError("Code cannot be whitespace-only")


def sanitize_export_name(export_name: str) -> str:
    """
    Sanitize export name to prevent path traversal and other attacks.

    Args:
        export_name: The export name to sanitize.

    Returns:
        Sanitized export name.

    Raises:
        ValueError: If export name is invalid.
    """
    if not export_name or not isinstance(export_name, str):
        raise ValueError("Export name must be a non-empty string")

    # Strip whitespace and normalize Unicode
    sanitized = export_name.strip()
    sanitized = unicodedata.normalize('NFC', sanitized)

    # Check length
    if len(sanitized) > MAX_EXPORT_NAME_LENGTH:
        raise ValueError(
            f"Export name exceeds maximum length of {MAX_EXPORT_NAME_LENGTH}"
        )

    # Use os.path.basename for robust path component extraction
    sanitized = os.path.basename(sanitized)

    # Reject if empty after sanitization
    if not sanitized:
        raise ValueError("Invalid export name after sanitization")

    # Reject hidden files/directories
    if sanitized.startswith('.'):
        raise ValueError("Export name cannot start with a dot")

    # Explicit check for any path separators (belt and suspenders)
    path_seps = ['/', '\\', os.sep]
    if os.altsep:
        path_seps.append(os.altsep)
    if any(sep in sanitized for sep in path_seps):
        raise ValueError("Export name cannot contain path separators")

    # Reject dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '\x00']
    for char in dangerous_chars:
        if char in sanitized:
            raise ValueError(f"Export name contains invalid character: {char}")

    # Reject reserved names
    if sanitized.lower() in ('.', '..', 'con', 'prn', 'aux', 'nul', 'com1', 'lpt1'):
        raise ValueError(f"Export name '{sanitized}' is reserved")

    return sanitized


def sanitize_docker_image_name(name: str) -> str:
    """
    Sanitize name for Docker image naming rules.

    Docker names must:
    - Be lowercase
    - Contain only a-z, 0-9, -, _
    - Be <= 128 characters

    Args:
        name: The name to sanitize.

    Returns:
        Sanitized Docker image name.
    """
    # Convert to lowercase
    sanitized = name.lower()

    # Replace underscores and dots with hyphens
    sanitized = sanitized.replace('_', '-').replace('.', '-')

    # Remove invalid characters
    sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)

    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')

    # Ensure non-empty
    if not sanitized:
        sanitized = "sandbox-export"

    # Truncate to max length
    if len(sanitized) > DOCKER_IMAGE_NAME_MAX_LENGTH:
        sanitized = sanitized[:DOCKER_IMAGE_NAME_MAX_LENGTH]

    return sanitized


def check_disk_space(directory: Path, required_bytes: int) -> Tuple[bool, str]:
    """
    Check if sufficient disk space is available for export.

    Args:
        directory: Directory to check space for
        required_bytes: Required free space in bytes

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Get disk usage statistics
        usage = shutil.disk_usage(str(directory))

        # Check if we have enough free space
        if usage.free < required_bytes:
            free_mb = usage.free / (1024 * 1024)
            required_mb = required_bytes / (1024 * 1024)
            return False, (
                f"Insufficient disk space. "
                f"Free: {free_mb:.1f}MB, Required: {required_mb:.1f}MB"
            )

        # Check if disk usage is critically high
        total_percent_used = (usage.used / usage.total) * 100
        if total_percent_used > DISK_USAGE_WARNING_PERCENT:
            return False, (
                f"Disk usage critical ({total_percent_used:.1f}%). "
                f"Please free up space before creating exports."
            )

        return True, "OK"

    except OSError as e:
        logger.error(f"Failed to check disk space: {e}")
        return False, f"Unable to check disk space: {e}"


def estimate_export_size(code: str, app_type: str) -> int:
    """
    Estimate export size in bytes before creation.

    Args:
        code: Application code
        app_type: Type of application ('flask' or 'streamlit')

    Returns:
        Estimated size in bytes
    """
    # Base file sizes (approximate)
    REQUIREMENTS_SIZE = 50  # requirements.txt
    DOCKERFILE_SIZE = 250  # Dockerfile
    COMPOSE_SIZE = 200  # docker-compose.yml
    README_SIZE = 600  # README.md

    # Code size (will be written to app.py)
    code_size = len(code.encode('utf-8'))

    # Overhead for directory entries, metadata
    OVERHEAD = 2048

    return REQUIREMENTS_SIZE + DOCKERFILE_SIZE + COMPOSE_SIZE + README_SIZE + code_size + OVERHEAD


def validate_export_requirements(code: str, export_name: str | None, exports_dir: Path) -> Tuple[bool, str | None]:
    """
    Validate all requirements for export before creation.

    This is a convenience function that combines multiple validations.

    Args:
        code: Application code to validate
        export_name: Optional export name to sanitize
        exports_dir: Directory to check for disk space

    Returns:
        Tuple of (is_valid: bool, error_message: str|None)
    """
    try:
        # Validate code
        validate_code(code)
    except ValueError as e:
        return False, str(e)

    # Validate and sanitize export name if provided
    if export_name:
        try:
            sanitize_export_name(export_name)
        except ValueError as e:
            return False, str(e)

    # Check disk space
    estimated_size = estimate_export_size(code, 'flask')  # Use largest type estimate
    if estimated_size > MAX_EXPORT_SIZE_BYTES:
        return False, f'Export size exceeds maximum ({MAX_EXPORT_SIZE_BYTES / (1024 * 1024):.0f}MB limit)'

    required_space = estimated_size + MIN_FREE_SPACE_BYTES
    space_ok, space_message = check_disk_space(exports_dir, required_space)
    if not space_ok:
        return False, space_message

    return True, None
