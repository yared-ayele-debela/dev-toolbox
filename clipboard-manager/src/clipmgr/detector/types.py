"""Type detection engine using lightweight heuristics and regular expressions."""

import json
import os
import re
from pathlib import Path
from typing import Optional

from clipmgr.models import ContentType

# URL regex matching standard protocols and common domain patterns
URL_REGEX = re.compile(
    r"^(?:(?:https?|ftp)://[^\s/$.?#].[^\s]*|"
    r"magnet:\?[^\s]+|"
    r"(?:www\.[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+[^\s]*)|"
    r"(?:localhost|127\.0\.0\.1)(?::\d{1,5})?(?:/[^\s]*)?)$",
    re.IGNORECASE,
)

# Common web/git URLs that don't always have scheme
DOMAIN_PATH_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*\.)+[a-zA-Z]{2,}(?::\d{1,5})?(?:/[^\s]*)?$",
    re.IGNORECASE,
)

# CSS/Design Colors
HEX_COLOR_REGEX = re.compile(
    r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)
RGB_COLOR_REGEX = re.compile(
    r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(?:\s*,\s*(?:0?\.\d+|1(?:\.0+)?|0))?\s*\)$",
    re.IGNORECASE,
)
HSL_COLOR_REGEX = re.compile(
    r"^hsla?\(\s*\d{1,3}(?:deg)?\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%(?:\s*,\s*(?:0?\.\d+|1(?:\.0+)?|0))?\s*\)$",
    re.IGNORECASE,
)

# File path pattern
FILE_PATH_PREFIXES = ("/", "~/", "./", "../", "file://")
KNOWN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg", ".sh", ".bash", ".zsh",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt", ".swift", ".php",
    ".rb", ".md", ".txt", ".csv", ".tsv", ".pdf", ".zip", ".tar", ".gz", ".xz",
    ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".so", ".deb", ".rpm",
}

# Code detection keywords and constructs
CODE_KEYWORDS = {
    "def ", "class ", "function ", "import ", "from ", "return ", "const ",
    "let ", "var ", "public ", "private ", "protected ", "void ", "struct ",
    "enum ", "fn ", "async ", "await ", "impl ", "package ", "func ", "interface ",
    "type ", "namespace ", "using ", "export default ", "export const ",
    "SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "CREATE TABLE ",
    "console.log(", "print(", "fmt.Println(", "std::cout", "println!",
}

CODE_BLOCK_PATTERNS = [
    re.compile(r"^#!\s*/[^\n]+"),                    # Shebang line
    re.compile(r"^\s*<(!DOCTYPE|[a-zA-Z0-9-]+)[^>]*>"),  # HTML/XML opening tag
    re.compile(r"[{};]\s*$"),                       # C-style line endings
    re.compile(r"\b(if|while|for|switch)\s*\(.*?\)\s*[{:]"), # Control structures
    re.compile(r"=>\s*[{]"),                        # Arrow function
    re.compile(r"def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(.*?\)\s*->?\s*.*?:"), # Python def
]


def is_url(text: str) -> bool:
    """Check if text is a valid web URL."""
    s = text.strip()
    if "\n" in s or len(s) < 4:
        return False
    return bool(URL_REGEX.match(s) or DOMAIN_PATH_REGEX.match(s))


def is_color(text: str) -> bool:
    """Check if text is a valid color specification (HEX, RGB, HSL)."""
    s = text.strip()
    if "\n" in s or len(s) > 35:
        return False
    return bool(
        HEX_COLOR_REGEX.match(s)
        or RGB_COLOR_REGEX.match(s)
        or HSL_COLOR_REGEX.match(s)
    )


def is_json(text: str) -> bool:
    """Check if text is a valid, structured JSON object or array."""
    s = text.strip()
    if len(s) < 2:
        return False
    if not ((s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))):
        return False
    try:
        parsed = json.loads(s)
        return isinstance(parsed, (dict, list)) and len(parsed) > 0
    except (ValueError, TypeError):
        return False


def is_file_path(text: str) -> bool:
    """Check if text looks like a Unix or local filesystem path."""
    s = text.strip()
    if "\n" in s or len(s) < 2:
        return False

    # Check file:// uri
    if s.startswith("file://"):
        return True

    # Check explicit prefixes
    if any(s.startswith(p) for p in FILE_PATH_PREFIXES):
        # Disallow simple arithmetic or flags like "./a -b" if it has spaces without quotes
        if " " not in s or (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            # If path exists on filesystem, definitely a path
            try:
                expanded = Path(os.path.expanduser(s.strip('"\'')))
                if expanded.exists():
                    return True
            except Exception:
                pass

            # Check if looks like a path structure
            if "/" in s:
                return True

    # Check if string has path separator and known extension
    if "/" in s and not s.startswith("http"):
        _, ext = os.path.splitext(s.lower())
        if ext in KNOWN_EXTENSIONS:
            return True

    return False


def is_code(text: str) -> bool:
    """Check if text looks like a programming code snippet."""
    s = text.strip()
    if len(s) < 5:
        return False

    lines = [line for line in s.splitlines() if line.strip()]
    if not lines:
        return False

    first_line = lines[0].strip()

    # 1. Shebang
    if first_line.startswith("#!") and ("bin/" in first_line or "env" in first_line):
        return True

    # 2. HTML/XML snippet
    if first_line.startswith("<") and (first_line.endswith(">") or "</" in s or "/>" in s):
        if re.search(r"<(html|head|body|div|span|p|script|style|link|template|table|tr|td|button|form|input)", s, re.IGNORECASE):
            return True

    # 3. Multi-line code heuristics
    code_signals = 0
    total_lines = len(lines)

    # Check for keyword matches
    for kw in CODE_KEYWORDS:
        if kw in s:
            code_signals += 2

    # Check line patterns
    for line in lines:
        stripped = line.strip()
        for pat in CODE_BLOCK_PATTERNS:
            if pat.search(stripped):
                code_signals += 1

        # Indentation after colon or opening brace
        if line.startswith("    ") or line.startswith("\t"):
            code_signals += 1

    # Score threshold based on lines
    threshold = 3 if total_lines > 1 else 2
    return code_signals >= threshold


def detect_content_type(content: str) -> ContentType:
    """Classify arbitrary clipboard content into a ContentType enum."""
    if not content or not content.strip():
        return ContentType.TEXT

    # Order of checks matters:
    # 1. Color (very specific, short single-line)
    if is_color(content):
        return ContentType.COLOR

    # 2. URL
    if is_url(content):
        return ContentType.URL

    # 3. File Path
    if is_file_path(content):
        return ContentType.FILE_PATH

    # 4. JSON
    if is_json(content):
        return ContentType.JSON

    # 5. Code
    if is_code(content):
        return ContentType.CODE

    # 6. Default to Plain Text
    return ContentType.TEXT
