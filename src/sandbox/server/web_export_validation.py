"""
Validation and Sanitization for Web Export Service.

This module provides input validation, sanitization, and security checks
for web application exports.

Security Features:
- Path traversal prevention via export name sanitization
- Input validation for code and export names
- Disk space validation to prevent DoS attacks
- Null byte detection
- Unicode normalization
"""

from __future__ import annotations

import os
import shutil
import unicodedata
from pathlib import Path
from typing import Tuple

# Constants
MAX_CODE_SIZE = 10 * 1024 * 1024  # 10 MB max code size
MAX_EXPORT_NAME_LENGTH = 100

# Disk space constants
MIN_FREE_SPACE_BYTES = 100 * 1024 * 1024  # 100 MB minimum free space
MAX_EXPORT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB max per export (including overhead)
DISK_USAGE_WARNING_PERCENT = 90  # Warn when disk usage exceeds this


class ValidationError(ValueError):
    """Raised when validation fails."""
    pass


def sanitize_export_name(export_name: str) -> str:
    """
    Sanitize export name to prevent path traversal and other attacks.

    Args:
        export_name: The export name to sanitize.

    Returns:
        Sanitized export name.

    Raises:
        ValidationError: If export name is invalid.
    """
    if not export_name or not isinstance(export_name, str):
        raise ValidationError("Export name must be a non-empty string")

    # Strip whitespace and normalize Unicode
    sanitized = export_name.strip()
    sanitized = unicodedata.normalize('NFC', sanitized)

    # Check length
    if len(sanitized) > MAX_EXPORT_NAME_LENGTH:
        raise ValidationError(
            f"Export name exceeds maximum length of {MAX_EXPORT_NAME_LENGTH}"
        )

    # Use os.path.basename for robust path component extraction
    sanitized = os.path.basename(sanitized)

    # Reject if empty after sanitization
    if not sanitized:
        raise ValidationError("Invalid export name after sanitization")

    # Reject hidden files/directories
    if sanitized.startswith('.'):
        raise ValidationError("Export name cannot start with a dot")

    # Explicit check for any path separators (belt and suspenders)
    path_seps = ['/', '\\', os.sep]
    if os.altsep:
        path_seps.append(os.altsep)
    if any(sep in sanitized for sep in path_seps):
        raise ValidationError("Export name cannot contain path separators")

    # Reject dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '\x00']
    for char in dangerous_chars:
        if char in sanitized:
            raise ValidationError(f"Export name contains invalid character: {char}")

    # Reject reserved names
    if sanitized.lower() in ('.', '..', 'con', 'prn', 'aux', 'nul', 'com1', 'lpt1'):
        raise ValidationError(f"Export name '{sanitized}' is reserved")

    return sanitized


def validate_code(code: str) -> None:
    """
    Validate code input.

    Args:
        code: The code to validate.

    Raises:
        ValidationError: If code is invalid.
    """
    if not code or not isinstance(code, str):
        raise ValidationError("Code must be a non-empty string")

    if len(code) > MAX_CODE_SIZE:
        raise ValidationError(
            f"Code exceeds maximum size of {MAX_CODE_SIZE / (1024 * 1024):.0f} MB"
        )

    # Check for null bytes
    if '\x00' in code:
        raise ValidationError("Code cannot contain null bytes")

    # Check for whitespace-only code
    if not code.strip():
        raise ValidationError("Code cannot be whitespace-only")


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
