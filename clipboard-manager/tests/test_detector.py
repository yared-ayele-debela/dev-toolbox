"""Unit tests for content type classification heuristics and regular expressions."""

import pytest
from clipmgr.detector.types import (
    detect_content_type,
    is_code,
    is_color,
    is_file_path,
    is_json,
    is_url,
)
from clipmgr.models import ContentType


class TestURLDetection:
    """Test URL heuristics and regex."""

    @pytest.mark.parametrize(
        "url_text",
        [
            "https://github.com/torvalds/linux",
            "http://example.com/api/v1/users?id=42&sort=desc",
            "ftp://files.example.org/downloads/archive.tar.gz",
            "magnet:?xt=urn:btih:d6b0ee6b4a229d47a32b217a1518f8e07a3f4e24",
            "www.nytimes.com/section/technology",
            "http://localhost:8080/dashboard",
            "http://127.0.0.1:3000/test",
            "gitlab.com/group/repo/-/issues/12",
        ],
    )
    def test_valid_urls(self, url_text: str) -> None:
        assert is_url(url_text) is True
        assert detect_content_type(url_text) == ContentType.URL

    @pytest.mark.parametrize(
        "invalid_text",
        [
            "This is just a regular sentence with no links.",
            "not a url at all",
            "https://invalid space in url.com",
            "multi\nline\nhttps://example.com",
            "",
            "   ",
        ],
    )
    def test_invalid_urls(self, invalid_text: str) -> None:
        assert is_url(invalid_text) is False


class TestColorDetection:
    """Test CSS and design color detection."""

    @pytest.mark.parametrize(
        "color_text",
        [
            "#fff",
            "#ffffff",
            "#1e1e2eff",
            "#89b4fa",
            "#F38BA8",
            "rgb(255, 128, 0)",
            "rgba(30, 30, 46, 0.95)",
            "hsl(217, 92%, 76%)",
            "hsla(217deg, 92%, 76%, 0.8)",
        ],
    )
    def test_valid_colors(self, color_text: str) -> None:
        assert is_color(color_text) is True
        assert detect_content_type(color_text) == ContentType.COLOR

    @pytest.mark.parametrize(
        "invalid_text",
        [
            "#zztop",
            "rgb(999, 999)",
            "blue",
            "#12345",  # 5 digits not standard
            "color: #ffffff;",
        ],
    )
    def test_invalid_colors(self, invalid_text: str) -> None:
        assert is_color(invalid_text) is False


class TestJSONDetection:
    """Test structured JSON detection."""

    def test_valid_json_objects(self) -> None:
        valid_obj = '{"name": "clipmgr", "version": "1.0.0", "active": true}'
        assert is_json(valid_obj) is True
        assert detect_content_type(valid_obj) == ContentType.JSON

    def test_valid_json_arrays(self) -> None:
        valid_arr = '[{"id": 1}, {"id": 2}, {"id": 3}]'
        assert is_json(valid_arr) is True
        assert detect_content_type(valid_arr) == ContentType.JSON

    @pytest.mark.parametrize(
        "invalid_text",
        [
            "{name: invalid_unquoted_keys}",
            "[1, 2, 3",
            "{",
            "{}",  # empty object
            "[]",  # empty array
            "Regular text",
        ],
    )
    def test_invalid_json(self, invalid_text: str) -> None:
        assert is_json(invalid_text) is False


class TestFilePathDetection:
    """Test filesystem path heuristics."""

    @pytest.mark.parametrize(
        "path_text",
        [
            "/etc/systemd/system/clipmgr.service",
            "/home/user/.config/clipmgr/config.yaml",
            "~/.local/share/clipboard.db",
            "./src/clipmgr/main.py",
            "../scripts/install.sh",
            "file:///usr/share/doc/package/README",
            "/var/log/syslog",
        ],
    )
    def test_valid_file_paths(self, path_text: str) -> None:
        assert is_file_path(path_text) is True
        assert detect_content_type(path_text) == ContentType.FILE_PATH

    @pytest.mark.parametrize(
        "non_paths",
        [
            "Just a sentence mentioning / and things",
            "2 / 4 = 0.5",
            "",
            "singleword",
        ],
    )
    def test_non_paths(self, non_paths: str) -> None:
        assert is_file_path(non_paths) is False


class TestCodeDetection:
    """Test programming language snippet heuristics."""

    def test_python_snippet(self) -> None:
        code = (
            "def calculate_total(items: list) -> float:\n"
            "    total = 0.0\n"
            "    for item in items:\n"
            "        total += item.price\n"
            "    return total"
        )
        assert is_code(code) is True
        assert detect_content_type(code) == ContentType.CODE

    def test_javascript_snippet(self) -> None:
        code = (
            "const fetchUserData = async (userId) => {\n"
            "    const response = await fetch(`/api/users/${userId}`);\n"
            "    return await response.json();\n"
            "};"
        )
        assert is_code(code) is True
        assert detect_content_type(code) == ContentType.CODE

    def test_html_snippet(self) -> None:
        html_code = '<div class="container">\n  <h1>Title</h1>\n  <p>Hello world</p>\n</div>'
        assert is_code(html_code) is True
        assert detect_content_type(html_code) == ContentType.CODE

    def test_sql_query(self) -> None:
        sql = "SELECT id, content, timestamp FROM clipboard_entries WHERE pinned = 1 ORDER BY timestamp DESC;"
        assert is_code(sql) is True
        assert detect_content_type(sql) == ContentType.CODE

    def test_shebang_script(self) -> None:
        sh = "#!/usr/bin/env bash\necho 'Running setup script'\nmkdir -p build"
        assert is_code(sh) is True
        assert detect_content_type(sh) == ContentType.CODE

    def test_plain_text_not_code(self) -> None:
        text = "Hey there! Are we still meeting for lunch today at 12:30 PM at the cafe downtown?"
        assert is_code(text) is False
        assert detect_content_type(text) == ContentType.TEXT
