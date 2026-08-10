"""Detector module providing type classification and privacy/secret detection."""

from clipmgr.detector.privacy import (
    calculate_shannon_entropy,
    detect_sensitive_content,
    is_password_manager_app,
    is_random_secret_string,
    mask_sensitive,
)
from clipmgr.detector.types import (
    detect_content_type,
    is_code,
    is_color,
    is_file_path,
    is_json,
    is_url,
)

__all__ = [
    "detect_content_type",
    "detect_sensitive_content",
    "calculate_shannon_entropy",
    "is_password_manager_app",
    "is_random_secret_string",
    "mask_sensitive",
    "is_url",
    "is_file_path",
    "is_code",
    "is_json",
    "is_color",
]
