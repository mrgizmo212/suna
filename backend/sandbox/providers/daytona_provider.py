from __future__ import annotations

from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxParams, Sandbox, SessionExecuteRequest
from daytona_api_client.models.workspace_state import WorkspaceState
from dotenv import load_dotenv

from utils.logger import logger
from utils.config import config, Configuration

from .base import SandboxProvider, SandboxHandle

load_dotenv()

class DaytonaHandle(SandboxHandle):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

class DaytonaProvider(SandboxProvider):
    def __init__(self) -> None:
        logger.debug("Initializing Daytona sandbox provider")
        daytona_config = DaytonaConfig(
            api_key=getattr(config, "SANDBOX_API_KEY", None) or getattr(config, "DAYTONA_API_KEY", None),
            server_url=getattr(config, "SANDBOX_SERVER_URL", None) or getattr(config, "DAYTONA_SERVER_URL", None),
            target=getattr(config, "SANDBOX_TARGET", None) or getattr(config, "DAYTONA_TARGET", None),
        )
        self.daytona = Daytona(daytona_config)
        logger.debug("Daytona client initialized")

    async def get_or_start_sandbox(self, sandbox_id: str) -> DaytonaHandle:
        logger.info(f"Getting or starting sandbox with ID: {sandbox_id}")
        sandbox = self.daytona.get_current_sandbox(sandbox_id)
        if sandbox.instance.state in (WorkspaceState.ARCHIVED, WorkspaceState.STOPPED):
            logger.info(f"Sandbox is in {sandbox.instance.state} state. Starting...")
            self.daytona.start(sandbox)
            sandbox = self.daytona.get_current_sandbox(sandbox_id)
            self.start_supervisord_session(sandbox)
        return DaytonaHandle(sandbox)

    def start_supervisord_session(self, sandbox: Sandbox) -> None:
        session_id = "supervisord-session"
        logger.info(f"Creating session {session_id} for supervisord")
        sandbox.process.create_session(session_id)
        sandbox.process.execute_session_command(
            session_id,
            SessionExecuteRequest(
                command="exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf",
                var_async=True,
            ),
        )
        logger.info(f"Supervisord started in session {session_id}")

    def create_sandbox(self, password: str, project_id: str | None = None) -> DaytonaHandle:
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
        self.start_supervisord_session(sandbox)
        logger.debug(f"Sandbox {sandbox.id} created")
        return DaytonaHandle(sandbox)
