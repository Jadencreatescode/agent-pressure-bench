from __future__ import annotations

import errno
import json
import os
import stat
from pathlib import Path, PurePath
from typing import Any, Protocol


class ToolError(RuntimeError):
    pass


class SandboxAdapter(Protocol):
    """Explicit external isolation boundary; core never executes host processes."""
    def execute(self, workspace: Path, action: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]: ...


class ToolExecutor:
    """Small file-tool surface anchored to an open workspace descriptor.

    On platforms without descriptor-relative operations and O_NOFOLLOW this
    implementation fails closed rather than claiming path confinement.
    """

    def __init__(self, root: Path, timeout: float = 10.0, sandbox: SandboxAdapter | None = None):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve(strict=True)
        self.timeout = timeout
        self.sandbox = sandbox
        needed = {os.open, os.mkdir, os.stat}
        if not hasattr(os, "O_NOFOLLOW") or not needed <= os.supports_dir_fd:
            raise ToolError("race-safe file tools require descriptor-relative filesystem operations")
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
        self._root_fd = os.open(self.root, flags)

    def __del__(self) -> None:
        fd = getattr(self, "_root_fd", None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self._root_fd = None

    @staticmethod
    def _parts(value: str) -> tuple[str, ...]:
        raw = PurePath(value)
        if not value or raw.is_absolute() or any(p in ("", ".", "..") for p in raw.parts):
            raise ToolError("path must be non-empty, relative, and contain no dot components")
        return raw.parts

    def _parent_fd(self, value: str, *, create: bool) -> tuple[int, str]:
        parts = self._parts(value)
        fd = os.dup(self._root_fd)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
        try:
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(part, 0o755, dir_fd=fd)
                    next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return fd, parts[-1]
        except (OSError, ValueError) as exc:
            os.close(fd)
            raise ToolError(f"unsafe or unavailable path: {value}") from exc

    def _write(self, value: str, content: str) -> dict[str, Any]:
        parent, leaf = self._parent_fd(value, create=True)
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
            fd = os.open(leaf, flags, 0o644, dir_fd=parent)
            try:
                data = content.encode("utf-8")
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
                return {"ok": True, "bytes": len(data)}
            finally:
                os.close(fd)
        except OSError as exc:
            raise ToolError(f"unsafe or unavailable path: {value}") from exc
        finally:
            os.close(parent)

    def _read(self, value: str) -> dict[str, Any]:
        parent, leaf = self._parent_fd(value, create=False)
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ToolError("not a regular file")
                with os.fdopen(os.dup(fd), "r", encoding="utf-8") as handle:
                    return {"ok": True, "content": handle.read()}
            finally:
                os.close(fd)
        except (OSError, UnicodeError) as exc:
            raise ToolError(f"unsafe or unavailable path: {value}") from exc
        finally:
            os.close(parent)

    def _list(self) -> list[str]:
        files: list[str] = []
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW

        def visit(fd: int, prefix: tuple[str, ...]) -> None:
            with os.scandir(fd) as entries:
                names = sorted(entry.name for entry in entries)
            for name in names:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    files.append("/".join((*prefix, name)))
                elif stat.S_ISDIR(info.st_mode):
                    child = os.open(name, directory_flags, dir_fd=fd)
                    try:
                        visit(child, (*prefix, name))
                    finally:
                        os.close(child)
        root = os.dup(self._root_fd)
        try:
            visit(root, ())
        except OSError as exc:
            raise ToolError("workspace changed during listing") from exc
        finally:
            os.close(root)
        return files

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolError("tool arguments must be an object")
        if name == "write_file":
            if set(arguments) != {"path", "content"} or not isinstance(arguments["path"], str) or not isinstance(arguments["content"], str):
                raise ToolError("write_file requires only string path and content")
            return self._write(arguments["path"], arguments["content"])
        if name == "read_file":
            if set(arguments) != {"path"} or not isinstance(arguments["path"], str):
                raise ToolError("read_file requires only a string path")
            return self._read(arguments["path"])
        if name == "list_files":
            if arguments:
                raise ToolError("list_files accepts no arguments")
            return {"ok": True, "files": self._list()}
        if name == "sandbox_action":
            if self.sandbox is None:
                raise ToolError("sandbox_action is disabled: no external sandbox adapter configured")
            if set(arguments) != {"action", "arguments"} or not isinstance(arguments["action"], str) or not isinstance(arguments["arguments"], dict):
                raise ToolError("sandbox_action requires action and arguments")
            return self.sandbox.execute(self.root, arguments["action"], arguments["arguments"], self.timeout)
        raise ToolError(f"unknown or disabled tool: {name}")


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "write_file", "description": "Write UTF-8 text in the task workspace", "parameters": {"type": "object", "additionalProperties": False, "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read UTF-8 text in the task workspace", "parameters": {"type": "object", "additionalProperties": False, "required": ["path"], "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "list_files", "description": "List regular workspace files", "parameters": {"type": "object", "additionalProperties": False, "properties": {}}}},
]


def sandbox_tool_schema() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "sandbox_action", "description": "Execute an action in an explicitly configured external sandbox", "parameters": {"type": "object", "additionalProperties": False, "required": ["action", "arguments"], "properties": {"action": {"type": "string"}, "arguments": {"type": "object"}}}}}
