# Tool Execution Fix - 2025-11-18

## Problem Statement
Agent would respond that it will use a tool but would stop without actually executing any tools. This affected ALL tool types: web search, file operations, shell commands, RAG, computer access, etc.

## Root Cause
Located in `/var/www/alpha.neuronests.com/suna/backend/core/agentpress/thread_manager.py` at lines 506 and 536:

### The Bug
```python
# Line 506 - Only enabled tool schemas for native calling
openapi_tool_schemas = self.tool_registry.get_openapi_schemas() if config.native_tool_calling else None

# Line 536 - Set tool_choice to "none" when native calling was disabled
tool_choice=tool_choice if config.native_tool_calling else "none"
```

### Why It Failed
1. The system was configured with `xml_tool_calling=True` and `native_tool_calling=False`
2. Line 536 would set `tool_choice="none"` because `native_tool_calling=False`
3. This explicitly told the LLM to NEVER use tools
4. Line 506 set `openapi_tool_schemas=None`, preventing tools from being passed to the LLM
5. Result: LLM would plan to use tools (based on system prompt) but couldn't actually call them

## The Fix
Changed the logic to enable tool calling when EITHER native OR XML tool calling is enabled:

```python
# Line 507-508 - Enable for EITHER mode
tools_enabled = config.native_tool_calling or config.xml_tool_calling
openapi_tool_schemas = self.tool_registry.get_openapi_schemas() if tools_enabled else None

# Line 538 - Use tool_choice when tools are enabled
tool_choice=tool_choice if tools_enabled else "none"
```

## Changes Made

### File: `/var/www/alpha.neuronests.com/suna/backend/core/agentpress/thread_manager.py`

**Lines 505-513:** Added logic to detect if tools are enabled via either method
**Lines 538:** Changed tool_choice logic to use `tools_enabled` flag
**Lines 511-513:** Added debug logging to trace tool configuration

## Testing Instructions

### 1. Restart Backend
```bash
cd /var/www/alpha.neuronests.com/suna/backend
# Stop the current backend process
# Restart the backend (method depends on your deployment)
```

### 2. Test All Tool Types

#### Web Search Tool
- Ask: "Search the web for the latest news about AI"
- Expected: Agent should execute web_search_tool and return results

#### File Operations
- Ask: "Create a test file called hello.txt with the content 'Hello World'"
- Expected: Agent should execute file creation tool

#### Shell Commands
- Ask: "List the files in the current directory"
- Expected: Agent should execute shell tool

#### RAG/Knowledge Base
- Ask a question that requires searching uploaded documents
- Expected: Agent should execute KB search tool

#### Data Providers
- Ask: "What's the current weather in San Francisco?"
- Expected: Agent should execute data provider tool

### 3. Check Debug Logs
Look for the new debug messages in backend logs:
```
🔧 Tool configuration: native_calling=False, xml_calling=True, tools_enabled=True
🔧 Tool schemas available: [number]
🔧 Tool choice setting: auto
```

These logs confirm tools are properly configured.

## Expected Behavior After Fix
1. Agent receives user message
2. Agent plans which tool to use (visible in response)
3. Agent EXECUTES the tool (new!)
4. Agent receives tool results
5. Agent provides final response with tool results

## Verification Checklist
- [ ] Backend restarted with new code
- [ ] Web search tool works
- [ ] File operations work
- [ ] Shell commands work
- [ ] RAG/KB queries work
- [ ] Data provider tools work
- [ ] Debug logs show `tools_enabled=True`
- [ ] Debug logs show `tool_choice=auto`

## Technical Details

### Configuration Flow
1. `AgentRunner.run()` creates `ProcessorConfig` with `xml_tool_calling=True, native_tool_calling=False`
2. `ThreadManager.run_thread()` receives this config
3. `ThreadManager._execute_run()` now correctly detects tools are enabled
4. LLM receives `tool_choice="auto"` and tool schemas
5. LLM can now actually call tools

### Why XML Mode Still Needs Tool Schemas
Even when using XML tool calling (`<tool>...</tool>` syntax), the LLM benefits from having tool schemas in the API call because:
- Modern LLMs use them to understand available functions
- They improve tool calling accuracy
- They enable the LLM to validate arguments

## Rollback Instructions
If issues occur, revert the change:
```bash
cd /var/www/alpha.neuronests.com/suna/backend/core/agentpress
git diff thread_manager.py  # Review changes
git checkout HEAD -- thread_manager.py  # Revert if needed
```

## Additional Notes
- This fix does not change the tool execution logic itself
- All tools remain configured as before
- Only the LLM's ability to call tools was fixed
- No database changes required
- No frontend changes required

