"""Unit tests for UNIX domain socket IPC communication."""

import time
from pathlib import Path

from quicklaunch.ipc import IPCServer, send_ipc_command


def test_ipc_ping_pong(temp_dir: Path) -> None:
    """Verify IPC ping command returns pong."""
    sock_path = temp_dir / "test.sock"
    server = IPCServer(socket_path=sock_path)
    assert server.start() is True

    try:
        response = send_ipc_command("ping", socket_path=sock_path, timeout=1.0)
        assert response == "pong"
    finally:
        server.stop()
        assert not sock_path.exists()


def test_ipc_custom_handler(temp_dir: Path) -> None:
    """Verify custom command handler processes requests."""
    sock_path = temp_dir / "test.sock"

    def handler(cmd: str) -> str:
        if cmd == "hello":
            return "world"
        return "unknown"

    server = IPCServer(socket_path=sock_path, command_handler=handler)
    assert server.start() is True

    try:
        response = send_ipc_command("hello", socket_path=sock_path, timeout=1.0)
        assert response == "world"

        res_unknown = send_ipc_command("other", socket_path=sock_path, timeout=1.0)
        assert res_unknown == "unknown"
    finally:
        server.stop()
