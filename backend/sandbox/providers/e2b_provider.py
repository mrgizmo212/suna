from __future__ import annotations

from typing import Any

from utils.logger import logger
from .base import SandboxProvider


class E2BProvider(SandboxProvider):
    """Simplified provider using the local filesystem as a sandbox."""

    def __init__(self, base_path: str = "/tmp/suna-sandbox") -> None:
        self.base_path = base_path
        logger.warning(
            "E2BProvider is a lightweight stub implementation. It only runs commands locally."
        )

    def create(self, password: str, project_id: str | None = None) -> Any:
        return self.base_path

    def start(self, sandbox: Any) -> Any:
        return sandbox

    def get_current_sandbox(self, sandbox_id: str) -> Any:
        return sandbox_id

    def exec(self, sandbox: Any, command: str, *, session: str | None = None, async_exec: bool = False) -> Any:
        import subprocess

        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=self.base_path)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
