import json
import base64
import asyncio
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import types
mock_dotenv = types.ModuleType("dotenv")
mock_dotenv.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", mock_dotenv)

# Stub utils.config before importing the tool
config_stub = types.ModuleType("utils.config")
config_stub.EnvMode = type("EnvMode", (), {"LOCAL": "local"})
class _Configuration:
    SANDBOX_IMAGE_NAME = "image"
    def __init__(self):
        self.ENV_MODE = "local"
        self.DAYTONA_API_KEY = "key"
        self.DAYTONA_SERVER_URL = "http://localhost"
        self.DAYTONA_TARGET = "target"
    def get(self, key, default=None):
        return getattr(self, key, default)
config_stub.Configuration = _Configuration
config_stub.config = _Configuration()
sys.modules.setdefault("utils.config", config_stub)

# Provide a minimal logger stub
logger_stub = types.ModuleType("utils.logger")
logger_stub.logger = types.SimpleNamespace(
    debug=lambda *a, **k: None,
    info=lambda *a, **k: None,
    warning=lambda *a, **k: None,
    error=lambda *a, **k: None,
)
sys.modules.setdefault("utils.logger", logger_stub)

# Minimal stub for agentpress.thread_manager to satisfy imports
thread_manager_stub = types.ModuleType("agentpress.thread_manager")
class _TM:
    pass
thread_manager_stub.ThreadManager = _TM
sys.modules.setdefault("agentpress.thread_manager", thread_manager_stub)

# Stub daytona_sdk module required by sandbox.tool_base
daytona_stub = types.ModuleType("daytona_sdk")
class _Sandbox:
    pass
daytona_stub.Sandbox = _Sandbox
class _Daytona:
    def __init__(self, *a, **k):
        pass
    def get_current_sandbox(self, *a, **k):
        return _Sandbox()
    def start(self, *a, **k):
        pass
    def create(self, *a, **k):
        return _Sandbox()
daytona_stub.Daytona = _Daytona
class _DaytonaConfig:
    def __init__(self, api_key=None, server_url=None, target=None):
        self.api_key = api_key
        self.server_url = server_url
        self.target = target
daytona_stub.DaytonaConfig = _DaytonaConfig
class _CreateSandboxParams:
    def __init__(self, *a, **k):
        pass
daytona_stub.CreateSandboxParams = _CreateSandboxParams
class _SessionExecuteRequest:
    def __init__(self, *a, **k):
        pass
daytona_stub.SessionExecuteRequest = _SessionExecuteRequest
sys.modules.setdefault("daytona_sdk", daytona_stub)

# Stub utils.s3_upload_utils
s3_stub = types.ModuleType("utils.s3_upload_utils")
async def _upload_base64_image(*args, **kwargs):
    return "http://image"
s3_stub.upload_base64_image = _upload_base64_image
sys.modules.setdefault("utils.s3_upload_utils", s3_stub)

# Stub daytona_api_client.models.workspace_state.WorkspaceState
dac_stub = types.ModuleType("daytona_api_client.models.workspace_state")
class _WS:
    ARCHIVED = "ARCHIVED"
    STOPPED = "STOPPED"
dac_stub.WorkspaceState = _WS
sys.modules.setdefault("daytona_api_client.models.workspace_state", dac_stub)

import pytest

from agent.tools.sb_browser_tool import SandboxBrowserTool

class DummyProcess:
    def __init__(self):
        self.command = None
    def exec(self, cmd, timeout=30):
        self.command = cmd
        class Resp:
            exit_code = 0
            result = json.dumps({"role":"assistant","content":"","message":"ok"})
        return Resp()

class DummySandbox:
    def __init__(self):
        self.process = DummyProcess()

class DummyThreadManager:
    async def add_message(self, thread_id, type, content, is_llm_message=False):
        return {"message_id": "msg1"}

def create_tool():
    tm = DummyThreadManager()
    tool = SandboxBrowserTool(project_id="p", thread_id="t", thread_manager=tm)
    return tool

def test_execute_browser_action_sanitizes_parameters():
    async def run():
        tool = create_tool()
        sandbox = DummySandbox()
        with patch.object(tool, "_ensure_sandbox", return_value=sandbox):
            tool._sandbox = sandbox
            await tool._execute_browser_action("test", {"text": "Hello'; rm -rf /"})
        return sandbox.process.command

    cmd = asyncio.run(run())
    assert "Hello'; rm -rf /" not in cmd
    encoded = base64.b64encode(json.dumps({"text": "Hello'; rm -rf /"}).encode()).decode()
    assert encoded in cmd


def test_execute_browser_action_returns_success_result():
    async def run():
        tool = create_tool()
        sandbox = DummySandbox()
        with patch.object(tool, "_ensure_sandbox", return_value=sandbox):
            tool._sandbox = sandbox
            result = await tool._execute_browser_action("test")
        return result

    result = asyncio.run(run())
    assert result.success
    data = json.loads(result.output)
    assert data["success"] is True
    assert data["message"] == "ok"
