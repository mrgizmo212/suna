from __future__ import annotations

from typing import Any
from utils.logger import logger
from utils.config import config

from .providers.base import SandboxProvider
from .providers.daytona_provider import DaytonaProvider
from .providers.e2b_provider import E2BProvider

_PROVIDER_MAP = {
    "daytona": DaytonaProvider,
    "e2b": E2BProvider,
    "codesandbox": DaytonaProvider,  # placeholder
}

_provider_instance: SandboxProvider | None = None


def get_provider() -> SandboxProvider:
    global _provider_instance
    if _provider_instance is None:
        provider_name = getattr(config, "SANDBOX_PROVIDER", "daytona").lower()
        cls = _PROVIDER_MAP.get(provider_name, DaytonaProvider)
        _provider_instance = cls()  # type: ignore[call-arg]
        logger.info(f"Using sandbox provider: {cls.__name__}")
    return _provider_instance


def create_sandbox(password: str, project_id: str | None = None) -> Any:
    provider = get_provider()
    return provider.create(password, project_id)


async def get_or_start_sandbox(sandbox_id: str) -> Any:
    provider = get_provider()
    if hasattr(provider, "ensure_running"):
        return provider.ensure_running(sandbox_id)  # type: ignore[attr-defined]
    sandbox = provider.get_current_sandbox(sandbox_id)
    return sandbox
