"""Security and privacy layer for detecting secrets, tokens, and password manager clips."""

import math
import re
from typing import Optional, Set, Tuple

# Known secret patterns with corresponding labels
SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS Secret Key", re.compile(r"(?i)\b(?:aws_secret_access_key|aws_secret)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    ("GitHub Token", re.compile(r"\b(ghp_[a-zA-Z0-9]{36,40}|gho_[a-zA-Z0-9]{36,40}|github_pat_[a-zA-Z0-9_]{82})\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")),
    ("Stripe Key", re.compile(r"\b[rs]k_live_[0-9a-zA-Z]{24,34}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b")),
    ("Private Key", re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")),
    ("JSON Web Token (JWT)", re.compile(r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b")),
    ("Generic Bearer Token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{25,}\b")),
    ("API Key Assignment", re.compile(r"(?i)\b(?:api_key|apikey|secret_key|client_secret|auth_token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]")),
]

# Known password managers and sensitive source applications (case-insensitive)
PASSWORD_MANAGERS: Set[str] = {
    "bitwarden",
    "1password",
    "keepass",
    "keepassxc",
    "lastpass",
    "dashlane",
    "nordpass",
    "enpass",
    "roboform",
    "authy",
    "google authenticator",
    "gnome-keyring",
    "kwallet",
    "seahorse",
    "secrets",  # GNOME Secrets
    "pass",
}


def calculate_shannon_entropy(text: str) -> float:
    """Calculate the Shannon entropy of a string (measure of randomness/unpredictability).

    High entropy (> 4.2 bits/char) on strings without spaces strongly indicates
    cryptographic keys, random passwords, or encoded binary tokens.
    """
    if not text:
        return 0.0

    length = len(text)
    freq: dict[str, int] = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1

    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def is_password_manager_app(source_app: Optional[str]) -> bool:
    """Check if the source application or window title belongs to a password manager."""
    if not source_app:
        return False
    app_lower = source_app.lower()
    for pm in PASSWORD_MANAGERS:
        if pm in app_lower:
            return True
    return False


def is_random_secret_string(text: str) -> bool:
    """Detect if a single-line string has characteristics of a generated password or key."""
    s = text.strip()
    # Passwords/tokens are usually single-line, 12 to 128 characters, without whitespace
    if "\n" in s or " " in s or len(s) < 12 or len(s) > 128:
        return False

    has_upper = any(c.isupper() for c in s)
    has_lower = any(c.islower() for c in s)
    has_digit = any(c.isdigit() for c in s)
    has_special = any(not c.isalnum() for c in s)

    # Count character diversity
    classes = sum([has_upper, has_lower, has_digit, has_special])
    entropy = calculate_shannon_entropy(s)

    # If at least 3 character classes and high entropy
    if classes >= 3 and entropy >= 3.8:
        return True

    # If length >= 24 and entropy >= 4.2 (e.g. hex / base64 keys)
    if len(s) >= 24 and entropy >= 4.2:
        return True

    return False


def detect_sensitive_content(content: str, source_app: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Determine whether clipboard content should be treated as sensitive/secret.

    Returns:
        A tuple of (is_sensitive: bool, reason_description: Optional[str]).
    """
    if not content or not content.strip():
        return False, None

    # 1. Source App Check (password manager window/app)
    if is_password_manager_app(source_app):
        return True, f"Copied from password manager: {source_app}"

    # 2. Known Regex Pattern Match
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return True, f"Detected pattern: {name}"

    # 3. High Entropy / Generated Password Check
    if is_random_secret_string(content):
        return True, "High entropy string (potential password or API secret)"

    return False, None


def mask_sensitive(content: str) -> str:
    """Return a masked representation for secure preview rendering."""
    return "•••••••••••••••• (Sensitive Content Hidden)"
