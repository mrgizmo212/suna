from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class SandboxHandle:
    """Opaque handle returned by a sandbox provider."""
    pass

class SandboxProvider(ABC):
    """Abstract sandbox provider interface."""

    @abstractmethod
    async def get_or_start_sandbox(self, sandbox_id: str) -> SandboxHandle:
        """Retrieve an existing sandbox by ID or start it if necessary."""
        raise NotImplementedError

    @abstractmethod
    def create_sandbox(self, password: str, project_id: str | None = None) -> SandboxHandle:
        """Create a new sandbox instance."""
        raise NotImplementedError

    @abstractmethod
    def start_supervisord_session(self, sandbox: SandboxHandle) -> None:
        """Ensure supervisord is running inside the sandbox."""
        raise NotImplementedError
