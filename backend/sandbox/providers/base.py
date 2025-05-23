from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SandboxProvider(ABC):
    """Abstract sandbox provider interface."""

    @abstractmethod
    def create(self, password: str, project_id: str | None = None) -> Any:
        """Create a new sandbox and return a handle to it."""

    @abstractmethod
    def start(self, sandbox: Any) -> Any:
        """Start a stopped sandbox."""

    @abstractmethod
    def get_current_sandbox(self, sandbox_id: str) -> Any:
        """Return sandbox handle by id."""

    @abstractmethod
    def exec(self, sandbox: Any, command: str, *, session: str | None = None, async_exec: bool = False) -> Any:
        """Execute a command inside a sandbox."""
