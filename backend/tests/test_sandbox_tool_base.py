import pytest
import sys
import types

# Provide stub modules so SandboxToolsBase can be imported without optional
# dependencies such as `openai` or `jwt`.
sys.modules.setdefault('openai', types.SimpleNamespace(OpenAIError=Exception))
sys.modules.setdefault('litellm', types.SimpleNamespace(token_counter=lambda *a, **k: 0, completion_cost=lambda *a, **k: 0))
import logging
fake_logger = logging.getLogger("test")
sys.modules.setdefault('utils.logger', types.SimpleNamespace(logger=fake_logger))

class DummyConfig:
    ENV_MODE = 'local'
    def __getattr__(self, name):
        return None

fake_config_module = types.SimpleNamespace(
    config=DummyConfig(),
    EnvMode=types.SimpleNamespace(PRODUCTION='production', STAGING='staging', LOCAL='local'),
    Configuration=DummyConfig,
)
sys.modules.setdefault('utils.config', fake_config_module)
sys.modules.setdefault('dotenv', types.SimpleNamespace(load_dotenv=lambda: None))
sys.modules.setdefault('daytona_sdk', types.SimpleNamespace(
    Daytona=object,
    DaytonaConfig=object,
    CreateSandboxParams=object,
    Sandbox=object,
    SessionExecuteRequest=object,
))
sys.modules.setdefault('daytona_api_client', types.SimpleNamespace())
sys.modules.setdefault('daytona_api_client.models', types.SimpleNamespace())
sys.modules.setdefault('daytona_api_client.models.workspace_state', types.SimpleNamespace(WorkspaceState=types.SimpleNamespace(ARCHIVED=None, STOPPED=None)))
sys.modules.setdefault('supabase', types.SimpleNamespace(create_async_client=lambda *a, **k: None, AsyncClient=object))
sys.modules.setdefault('sandbox.sandbox', types.SimpleNamespace(get_or_start_sandbox=lambda *_: None))

from sandbox.tool_base import SandboxToolsBase


class DummyTool(SandboxToolsBase):
    pass


def test_sandbox_property_uninitialized():
    tool = DummyTool('proj')
    with pytest.raises(RuntimeError):
        _ = tool.sandbox


def test_sandbox_id_property_uninitialized():
    tool = DummyTool('proj')
    with pytest.raises(RuntimeError):
        _ = tool.sandbox_id


def test_clean_path_method():
    tool = DummyTool('proj')
    assert tool.clean_path('/workspace/foo/bar') == 'foo/bar'
    assert tool.clean_path('workspace/foo/bar') == 'foo/bar'
    assert tool.clean_path('foo/bar') == 'foo/bar'
