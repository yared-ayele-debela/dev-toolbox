"""UNIX domain socket IPC for single-instance control, toggling, and daemon communication."""

import logging
import os
import select
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from clipmgr.constants import SOCKET_FILE, secure_file

logger = logging.getLogger(__name__)


def send_ipc_command(
    command: str, socket_path: Optional[Path] = None, timeout: float = 2.0
) -> Optional[str]:
    """Send a command string to the running ClipMgr daemon via UNIX socket.

    Returns:
        Daemon's string response, or None if daemon is unreachable.
    """
    sock_path = socket_path or SOCKET_FILE
    if not sock_path.exists():
        return None

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(sock_path))
        payload = f"{command.strip()}\n".encode("utf-8")
        client.sendall(payload)

        response_chunks = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response_chunks.append(chunk)
            if b"\n" in chunk:
                break

        response = b"".join(response_chunks).decode("utf-8").strip()
        return response
    except (ConnectionRefusedError, FileNotFoundError, socket.timeout, BrokenPipeError):
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


class IPCServer:
    """Listens on a UNIX domain socket for control commands from CLI or global hotkeys."""

    def __init__(
        self,
        socket_path: Optional[Path] = None,
        command_handler: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.socket_path = socket_path or SOCKET_FILE
        self.command_handler = command_handler
        self._server_sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> bool:
        """Bind socket and start listener thread."""
        try:
            self.socket_path.parent.mkdir(parents=True, exist_ok=True)
            if self.socket_path.exists():
                # Check if old daemon is still alive
                ping_res = send_ipc_command("ping", self.socket_path, timeout=0.5)
                if ping_res == "pong":
                    logger.warning("Another instance of ClipMgr is already running.")
                    return False
                # Remove stale socket
                try:
                    self.socket_path.unlink()
                except OSError:
                    pass

            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(str(self.socket_path))
            self._server_sock.listen(10)
            self._server_sock.setblocking(False)
            secure_file(self.socket_path)

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._serve_loop, daemon=True)
            self._thread.start()
            logger.info("IPC Server listening on %s", self.socket_path)
            return True

        except Exception as e:
            logger.error("Failed to start IPC server: %s", e)
            return False

    def _serve_loop(self) -> None:
        """Accept connections and dispatch requests."""
        while not self._stop_event.is_set():
            try:
                readable, _, _ = select.select([self._server_sock], [], [], 0.5)
                if not readable:
                    continue

                conn, _ = self._server_sock.accept()
                conn.settimeout(2.0)
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.debug("Error in IPC serve loop: %s", e)

    def _handle_client(self, conn: socket.socket) -> None:
        """Read command from client, dispatch to handler, and return reply."""
        try:
            data = b""
            # Read up to 2MB for potential large payloads (like ingest)
            while b"\n" not in data and len(data) < 2 * 1024 * 1024:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            cmd = data.decode("utf-8").strip()
            if not cmd:
                return

            response = "ok"
            if cmd == "ping":
                response = "pong"
            elif self.command_handler:
                try:
                    handler_res = self.command_handler(cmd)
                    if handler_res is not None:
                        response = str(handler_res)
                except Exception as e:
                    logger.error("Error executing IPC command handler for '%s': %s", cmd[:30], e)
                    response = f"error: {e}"

            conn.sendall(f"{response}\n".encode("utf-8"))
        except Exception as e:
            logger.debug("Error handling IPC client: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self) -> None:
        """Stop server and clean up socket file."""
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        logger.info("IPC Server stopped and socket removed")
