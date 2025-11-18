# Self-Hosting Modifications to Kortix/Suna

**Date:** 2025-11-17  
**Reason:** Self-hosted deployment without AWS Bedrock

---

## Deviation from Official Kortix/Suna

The official Kortix/Suna production deployment uses **AWS Bedrock** for cost-optimized Claude model access. 

For self-hosting without AWS infrastructure, we've modified the model provider configuration.

---

## Changes Made

### 1. Model Provider Configuration

**File:** `backend/core/ai_models/registry.py`  
**Lines:** 7-19

**Original:**
```python
# Production must use Bedrock
SHOULD_USE_ANTHROPIC = config.ENV_MODE == EnvMode.LOCAL and bool(config.ANTHROPIC_API_KEY)
FREE_MODEL_ID = "bedrock/..."  # AWS Bedrock ARN
```

**Modified:**
```python
# Self-hosting modification: Use OpenRouter
SHOULD_USE_OPENROUTER = bool(config.OPENROUTER_API_KEY)

if SHOULD_USE_OPENROUTER:
    FREE_MODEL_ID = "openai/gpt-5.1-chat"  # Via OpenRouter
    PREMIUM_MODEL_ID = "openai/gpt-5.1-chat"
```

### 2. Default Suna Model

**File:** `backend/core/suna_config.py`  
**Line:** 7

**Original:**
```python
"model": "claude-haiku-4.5",
```

**Modified:**
```python
"model": "openai/gpt-5.1-chat",  # Via OpenRouter - Latest GPT (Nov 2025)
```

### 3. OpenRouter Models Added

Added to registry (lines 30-76):
- ✅ **openai/gpt-5.1-chat** (Latest, recommended)
- ✅ **openai/gpt-5.1** (Base model)

---

## Why OpenRouter?

**Benefits for self-hosting:**
1. ✅ **Single API key** for 100+ models (Anthropic, OpenAI, Google, Meta, etc.)
2. ✅ **No AWS account** required
3. ✅ **Dynamic model discovery** - new models auto-available
4. ✅ **Flexible pricing** - pay-as-you-go
5. ✅ **Same code** works across providers

**Trade-offs vs Official Kortix:**
- ⚠️ **Upstream divergence** - must re-apply changes on updates
- ⚠️ **Different cost structure** - OpenRouter vs AWS Bedrock pricing
- ⚠️ **Not officially supported** - Kortix team uses Bedrock

---

## Configuration

**Environment Variables Required:**
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

**Current Configuration:**
- Provider: OpenRouter
- Default Model: openai/gpt-5.1-chat
- API Key: Configured ✅

---

## Future Enhancement (Path 2)

**Plan:** Build superadmin model management UI

**Will enable:**
- Dynamic model fetching from OpenRouter API
- Superadmin-controlled model enable/disable
- Per-model parameter configuration
- Runtime provider switching
- No code changes for model updates

**See:** `docs/path-2-architecture.md` (when implemented)

---

## Rollback to Official Kortix

To revert to official Bedrock setup:

1. Get AWS Bedrock bearer token
2. Add to `.env`:
   ```bash
   AWS_BEARER_TOKEN_BEDROCK=your_token
   ```
3. Revert changes to:
   - `backend/core/ai_models/registry.py` (lines 7-76)
   - `backend/core/suna_config.py` (line 7)
4. Restart services

---

## Maintenance Notes

**On Upstream Updates:**
- Check if `registry.py` or `suna_config.py` changed
- Re-apply OpenRouter modifications if needed
- Document any conflicts

**Current Kortix Version:** Fresh clone (Nov 17, 2025)  
**Last Verified:** 2025-11-17

---

**Maintained by:** Self-hosting team  
**Contact:** adam@truetradinggroup.com

