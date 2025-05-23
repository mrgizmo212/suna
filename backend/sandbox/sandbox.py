from __future__ import annotations

"""Sandbox provider loader.

This module exposes helper functions that delegate to the sandbox provider
selected via configuration. Daytona remains the default provider for
backwards compatibility, but additional providers can be plugged in.
"""

from utils.config import config
from utils.logger import logger

from .providers.base import SandboxProvider, SandboxHandle
from .providers.daytona_provider import DaytonaProvider
from .providers.e2b_provider import E2BProvider

_provider: SandboxProvider | None = None


def _get_provider() -> SandboxProvider:
    global _provider
    if _provider is None:
        provider_name = getattr(config, "SANDBOX_PROVIDER", "daytona").lower()
        if provider_name == "e2b":
            _provider = E2BProvider()
        else:
            _provider = DaytonaProvider()
        logger.info(f"Using sandbox provider: {provider_name}")
    return _provider


def provider() -> SandboxProvider:
    """Expose the configured sandbox provider instance."""
    return _get_provider()


async def get_or_start_sandbox(sandbox_id: str) -> SandboxHandle:
    """Retrieve or start a sandbox using the configured provider."""
    return await _get_provider().get_or_start_sandbox(sandbox_id)


def create_sandbox(password: str, project_id: str | None = None) -> SandboxHandle:
    """Create a new sandbox using the configured provider."""
    return _get_provider().create_sandbox(password, project_id)
