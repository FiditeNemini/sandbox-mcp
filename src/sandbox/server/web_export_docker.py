"""
Docker Build Operations for Web Export Service.

This module handles Docker image building for exported web applications.

Security Features:
- Docker image name sanitization
- Build timeout enforcement
- Process isolation
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Constants
DOCKER_BUILD_TIMEOUT = 1800  # 30 minutes
DOCKER_IMAGE_NAME_MAX_LENGTH = 128

logger = logging.getLogger(__name__)


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


def check_docker_available() -> bool:
    """
    Check if Docker is available on the system.

    Returns:
        True if Docker is available, False otherwise.
    """
    try:
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_docker_image(
    export_dir: Path,
    export_name: str,
    image_prefix: str = 'sandbox-'
) -> Tuple[bool, Optional[str], str, str]:
    """
    Build Docker image for an exported web application.

    Args:
        export_dir: Path to the export directory.
        export_name: Name of the export.
        image_prefix: Prefix for the Docker image name.

    Returns:
        Tuple of (success: bool, image_name: Optional[str], stdout: str, stderr: str)
    """
    dockerfile_path = export_dir / "Dockerfile"
    if not dockerfile_path.exists():
        logger.warning(f"No Dockerfile found in export {export_name}")
        return False, None, "", "No Dockerfile found"

    try:
        # Sanitize image name for Docker
        image_name = f'{image_prefix}{sanitize_docker_image_name(export_name)}'

        result = subprocess.run(
            ['docker', 'build', '-t', image_name, str(export_dir)],
            capture_output=True,
            text=True,
            timeout=DOCKER_BUILD_TIMEOUT
        )

        if result.returncode == 0:
            logger.info(f"Docker image built successfully: {image_name}")
            return True, image_name, result.stdout, result.stderr
        else:
            logger.warning(f"Docker build failed for {export_name}: {result.stderr}")
            return False, None, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        logger.warning(f"Docker build timed out for {export_name}")
        return False, None, "", "Docker build timed out"
    except Exception as e:
        logger.error(f"Failed to build Docker image: {e}")
        return False, None, "", str(e)


def remove_docker_image(
    export_name: str,
    image_prefix: str = 'sandbox-'
) -> Tuple[bool, str]:
    """
    Remove Docker image for an exported web application.

    Args:
        export_name: Name of the export.
        image_prefix: Prefix for the Docker image name.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        image_name = f'{image_prefix}{sanitize_docker_image_name(export_name)}'
        result = subprocess.run(
            ['docker', 'rmi', image_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, f"Docker image '{image_name}' removed"
        else:
            return False, f"Docker image removal failed: {result.stderr}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"Docker cleanup error: {e}"
