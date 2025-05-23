from __future__ import annotations

import asyncio
from typing import Any
from dotenv import load_dotenv
from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxParams, SessionExecuteRequest
from daytona_api_client.models.workspace_state import WorkspaceState

from utils.logger import logger
from utils.config import config, Configuration
from .base import SandboxProvider


load_dotenv()


class DaytonaProvider(SandboxProvider):
    """Sandbox provider backed by Daytona."""

    def __init__(self) -> None:
        logger.debug("Initializing Daytona sandbox configuration")
        daytona_config = DaytonaConfig(
            api_key=config.DAYTONA_API_KEY,
            server_url=config.DAYTONA_SERVER_URL,
            target=config.DAYTONA_TARGET,
        )
        self.daytona = Daytona(daytona_config)
        logger.debug("Daytona client initialized")

    def create(self, password: str, project_id: str | None = None) -> Any:
        logger.debug("Creating new Daytona sandbox environment")
        labels = {"id": project_id} if project_id else None
        params = CreateSandboxParams(
            image=Configuration.SANDBOX_IMAGE_NAME,
            public=True,
            labels=labels,
            env_vars={
                "CHROME_PERSISTENT_SESSION": "true",
                "RESOLUTION": "1024x768x24",
                "RESOLUTION_WIDTH": "1024",
                "RESOLUTION_HEIGHT": "768",
                "VNC_PASSWORD": password,
                "ANONYMIZED_TELEMETRY": "false",
                "CHROME_PATH": "",
                "CHROME_USER_DATA": "",
                "CHROME_DEBUGGING_PORT": "9222",
                "CHROME_DEBUGGING_HOST": "localhost",
                "CHROME_CDP": "",
            },
            resources={"cpu": 2, "memory": 4, "disk": 5},
        )
        sandbox = self.daytona.create(params)
        self._start_supervisord_session(sandbox)
        logger.debug("Sandbox environment successfully initialized")
        return sandbox

    def start(self, sandbox: Any) -> Any:
        self.daytona.start(sandbox)
        return sandbox

    def get_current_sandbox(self, sandbox_id: str) -> Any:
        return self.daytona.get_current_sandbox(sandbox_id)

    def exec(self, sandbox: Any, command: str, *, session: str | None = None, async_exec: bool = False) -> Any:
        session = session or "default"
        sandbox.process.create_session(session)
        req = SessionExecuteRequest(command=command, var_async=async_exec)
        return sandbox.process.execute_session_command(session, req)

    def ensure_running(self, sandbox_id: str):
        sandbox = self.daytona.get_current_sandbox(sandbox_id)
        if sandbox.instance.state in (WorkspaceState.ARCHIVED, WorkspaceState.STOPPED):
            self.start(sandbox)
            # refresh after short delay
            asyncio.sleep(0.1)
            sandbox = self.daytona.get_current_sandbox(sandbox_id)
            self._start_supervisord_session(sandbox)
        return sandbox

    def _start_supervisord_session(self, sandbox: Any) -> None:
        session_id = "supervisord-session"
        try:
            sandbox.process.create_session(session_id)
            sandbox.process.execute_session_command(
                session_id,
                SessionExecuteRequest(
                    command=Configuration.SANDBOX_ENTRYPOINT,
                    var_async=True,
                ),
            )
        except Exception as e:
            logger.error("Error starting supervisord session: %s", e)
            raise
