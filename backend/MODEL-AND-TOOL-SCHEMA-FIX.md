# Model Names and Tool Schema Fix - 2025-11-18

## Problem Statement
Three critical issues were preventing agent execution:

1. **Invalid Anthropic Model Names**: Using non-existent models `claude-haiku-4.5` and `claude-sonnet-4.5`
2. **Invalid OpenAI Tool Schema**: `create_tasks` tool had `anyOf` at top level (unsupported by OpenAI)
3. **Confusion about LiteLLM**: Unclear if system should use LiteLLM for routing

## Error Messages
```
litellm.NotFoundError: AnthropicException - model: claude-haiku-4.5
litellm.NotFoundError: AnthropicException - model: claude-sonnet-4.5  
litellm.BadRequestError: OpenAIException - Invalid schema for function 'create_tasks': 
schema must have type 'object' and not have 'oneOf'/'anyOf'/'allOf'/'enum'/'not' at the top level
```

## Root Causes

### Issue 1: Non-Existent Model Names
The codebase was using fictional model names:
- `anthropic/claude-haiku-4.5` ❌ (does not exist)
- `anthropic/claude-sonnet-4.5` ❌ (does not exist)

These models were referenced in:
- `core/ai_models/registry.py` (lines 9-10, 25, 50)
- `core/services/llm.py` (fallback configuration lines 108-117)
- `core/suna_config.py` (default model line 7)

### Issue 2: Invalid Tool Schema
The `create_tasks` tool in `task_list_tool.py` used `anyOf` at the root level of the parameters schema (lines 224-233), which OpenAI's function calling API explicitly does not support.

### Issue 3: LiteLLM Usage
**Answer: YES, you SHOULD use LiteLLM**. It's your unified LLM routing layer that provides:
- Multi-provider support (OpenRouter, Anthropic, OpenAI, etc.)
- Automatic fallback mechanisms
- Cost tracking
- Unified API interface

## Fixes Applied

### Fix 1: Updated Model Names

**Changed from invalid names to valid Anthropic models:**

```python
# Before (WRONG)
FREE_MODEL_ID = "anthropic/claude-haiku-4.5"
PREMIUM_MODEL_ID = "anthropic/claude-sonnet-4.5"

# After (CORRECT)
FREE_MODEL_ID = "anthropic/claude-3-5-haiku-latest"
PREMIUM_MODEL_ID = "anthropic/claude-3-5-sonnet-latest"
```

**Updated model registry:**
- `anthropic/claude-3-5-sonnet-latest` - Premium model (Claude 3.5 Sonnet)
- `anthropic/claude-3-5-haiku-latest` - Free/fast model (Claude 3.5 Haiku)

**Added backward compatibility aliases:**
- Old names (`claude-haiku-4.5`, `claude-sonnet-4.5`) are aliased to new correct models
- This ensures existing configurations don't break

**Updated fallback chains:**
```python
# Sonnet 3.5 → Haiku 3.5 → GPT-4o
# Haiku 3.5 → Sonnet 3.5 (upgrade if needed)
```

### Fix 2: Fixed Tool Schema

**Removed `anyOf` from top-level parameters:**

```python
# Before (INVALID for OpenAI)
"parameters": {
    "type": "object",
    "properties": { ... },
    "anyOf": [  # ❌ OpenAI doesn't support this at top level
        {"required": ["sections"]},
        {"required": ["task_contents"], "anyOf": [...]}
    ]
}

# After (VALID)
"parameters": {
    "type": "object",
    "properties": { ... },
    "required": []  # ✅ All parameters optional, validation in description
}
```

**Changes:**
- Made all parameters optional at schema level
- Moved validation logic to description text
- Tool function still validates parameters at runtime

### Fix 3: LiteLLM Confirmation

**LiteLLM is correctly configured and SHOULD be used:**
- Provides unified interface across multiple LLM providers
- Automatic fallback when primary models fail
- Cost tracking and monitoring
- Retry mechanisms with configurable delays

## Files Modified

### 1. `/var/www/alpha.neuronests.com/suna/backend/core/ai_models/registry.py`
- Lines 9-10: Updated FREE_MODEL_ID and PREMIUM_MODEL_ID
- Lines 25-28: Changed Sonnet model ID and aliases
- Lines 50-53: Changed Haiku model ID and aliases

### 2. `/var/www/alpha.neuronests.com/suna/backend/core/services/llm.py`
- Lines 108-117: Updated fallback chain model names

### 3. `/var/www/alpha.neuronests.com/suna/backend/core/suna_config.py`
- Line 7: Updated default model name

### 4. `/var/www/alpha.neuronests.com/suna/backend/core/tools/task_list_tool.py`
- Lines 182-227: Removed `anyOf` from schema, made parameters optional

## Testing Required

### 1. Test Model Availability
```bash
# Check logs for successful model initialization
docker compose logs backend | grep -i "claude-3-5"
```

### 2. Test Tool Execution
Try any tool (should work now):
- Web search: "Search for latest AI news"
- File operations: "Create test.txt"
- Task creation: "Create tasks for building a website"

### 3. Test Fallback Chain
If primary model fails, should automatically fallback to secondary:
1. claude-3-5-sonnet-latest → claude-3-5-haiku-latest → openai/gpt-4o

## Expected Behavior After Fix

1. ✅ Models resolve to valid Anthropic Claude 3.5 models
2. ✅ LiteLLM successfully routes requests to OpenRouter
3. ✅ Tool schemas pass OpenAI validation
4. ✅ Agent can execute all tools without schema errors
5. ✅ Fallback mechanisms work when primary model unavailable

## Verification Checklist

- [ ] Backend rebuilds without errors
- [ ] No "model not found" errors in logs
- [ ] No "invalid schema" errors in logs
- [ ] Tools execute successfully (web search, files, etc.)
- [ ] Fallback works if primary model unavailable
- [ ] Cost tracking works correctly

## Additional Notes

### Model Naming Convention
Anthropic uses this format: `claude-{version}-{variant}-{date}`
- Example: `claude-3-5-sonnet-20241022`
- Or the `-latest` suffix for current stable version

### Why -latest suffix?
- Points to most recent stable version automatically
- Avoids hardcoding specific date versions
- OpenRouter and LiteLLM support this format

### Tool Schema Best Practices
For OpenAI function calling:
- ✅ `type: object` at root level
- ✅ Use `required` array for mandatory fields
- ❌ NO `anyOf`/`oneOf`/`allOf` at root level
- ❌ NO `enum` at root level (but OK in nested properties)
- ✅ Use descriptions to explain parameter combinations

## Rollback Instructions

If issues occur:
```bash
cd /var/www/alpha.neuronests.com/suna/backend
git diff core/ai_models/registry.py
git diff core/services/llm.py
git diff core/suna_config.py
git diff core/tools/task_list_tool.py

# Revert if needed
git checkout HEAD -- core/ai_models/registry.py core/services/llm.py core/suna_config.py core/tools/task_list_tool.py
```

## Resources

- Anthropic Models: https://docs.anthropic.com/en/docs/about-claude/models
- LiteLLM Documentation: https://docs.litellm.ai/
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- OpenRouter Models: https://openrouter.ai/models

