from __future__ import annotations

from utils.logger import logger
from .base import SandboxProvider, SandboxHandle

class E2BHandle(SandboxHandle):
    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id

class E2BProvider(SandboxProvider):
    """Placeholder provider for e2b or other self-hosted sandbox implementation."""

    def __init__(self) -> None:
        logger.debug("Initializing E2B sandbox provider")
        # TODO: initialize client here

    async def get_or_start_sandbox(self, sandbox_id: str) -> E2BHandle:
        logger.warning("E2BProvider.get_or_start_sandbox is not implemented")
        return E2BHandle(sandbox_id)

    def start_supervisord_session(self, sandbox: SandboxHandle) -> None:
        logger.warning("E2BProvider.start_supervisord_session is not implemented")

    def create_sandbox(self, password: str, project_id: str | None = None) -> E2BHandle:
        logger.warning("E2BProvider.create_sandbox is not implemented")
        return E2BHandle("placeholder")
