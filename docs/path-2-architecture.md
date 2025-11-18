# Path 2: Dynamic OpenRouter Model Management (Superadmin Control)

**Status:** Architecture Design  
**Priority:** Future Enhancement  
**Date:** 2025-11-17

---

## Overview

Build a proper **superadmin-controlled model management system** that:
- ✅ Dynamically fetches models from OpenRouter API
- ✅ Allows superadmin to enable/disable models
- ✅ Supports per-model parameter configuration
- ✅ Stores configuration in database (not code)
- ✅ Auto-updates when OpenRouter adds new models

---

## Architecture Components

### 1. Database Schema

```sql
-- Table: model_configurations
-- Stores which models are enabled and their custom parameters
CREATE TABLE IF NOT EXISTS public.model_configurations (
    model_id VARCHAR PRIMARY KEY,  -- e.g., "openai/gpt-5.1-chat"
    provider VARCHAR NOT NULL,  -- e.g., "openrouter", "anthropic", "openai"
    is_enabled BOOLEAN DEFAULT false,
    is_recommended BOOLEAN DEFAULT false,
    priority INT DEFAULT 50,
    tier_availability VARCHAR[] DEFAULT ARRAY['paid'],
    
    -- Custom LiteLLM parameters (JSON)
    custom_params JSONB DEFAULT '{}',
    -- Example: {"temperature": 0.7, "max_tokens": 4096, "top_p": 0.9}
    
    -- Pricing override (if different from OpenRouter API)
    custom_pricing JSONB DEFAULT NULL,
    -- Example: {"input_per_million": 2.50, "output_per_million": 10.00}
    
    -- Metadata
    display_name VARCHAR,
    description TEXT,
    context_window INT,
    capabilities VARCHAR[] DEFAULT ARRAY[]::VARCHAR[],
    
    -- Audit fields
    created_by UUID REFERENCES auth.users(id),
    modified_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX idx_model_configs_enabled ON public.model_configurations(is_enabled, priority DESC);
CREATE INDEX idx_model_configs_provider ON public.model_configurations(provider);

-- Row Level Security
ALTER TABLE public.model_configurations ENABLE ROW LEVEL SECURITY;

-- Policy: Anyone can view enabled models
CREATE POLICY "Anyone can view enabled models" ON public.model_configurations
    FOR SELECT USING (is_enabled = true);

-- Policy: Only super_admin can modify
CREATE POLICY "Only super_admin can manage models" ON public.model_configurations
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.user_roles
            WHERE user_id = auth.uid()
            AND role = 'super_admin'
        )
    );

-- Policy: Service role has full access
CREATE POLICY "Service role manages models" ON public.model_configurations
    FOR ALL USING (auth.role() = 'service_role');
```

---

```sql
-- Table: openrouter_model_cache
-- Caches the full model list from OpenRouter API
CREATE TABLE IF NOT EXISTS public.openrouter_model_cache (
    model_id VARCHAR PRIMARY KEY,
    model_data JSONB NOT NULL,  -- Full response from OpenRouter
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT false
);

-- Index for cache refresh
CREATE INDEX idx_openrouter_cache_stale ON public.openrouter_model_cache(fetched_at DESC);

-- Auto-mark stale after 1 hour
CREATE OR REPLACE FUNCTION mark_openrouter_cache_stale()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.openrouter_model_cache
    SET is_stale = true
    WHERE fetched_at < NOW() - INTERVAL '1 hour';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER openrouter_cache_stale_check
    AFTER INSERT OR UPDATE ON public.openrouter_model_cache
    FOR EACH ROW
    EXECUTE FUNCTION mark_openrouter_cache_stale();
```

---

### 2. Backend Service

**File:** `backend/core/ai_models/openrouter_sync.py`

```python
import httpx
from typing import List, Dict, Any
from core.utils.config import config
from core.utils.logger import logger
from core.services.supabase import DBConnection

class OpenRouterSync:
    """Service to sync models from OpenRouter API"""
    
    OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
    CACHE_TTL_SECONDS = 3600  # 1 hour
    
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")
    
    async def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Fetch all available models from OpenRouter API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.OPENROUTER_API_BASE}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": config.NEXT_PUBLIC_URL or "https://alpha.neuronests.com",
                        "X-Title": "Suna AI Platform"
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                models = data.get('data', [])
                logger.info(f"Fetched {len(models)} models from OpenRouter")
                return models
                
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            return []
    
    async def sync_to_cache(self, force: bool = False) -> int:
        """Sync OpenRouter models to database cache"""
        db = DBConnection()
        client = await db.client
        
        # Check if cache is stale
        if not force:
            result = await client.table('openrouter_model_cache')\
                .select('COUNT(*)')\
                .eq('is_stale', False)\
                .execute()
            
            if result.data and result.data[0]['count'] > 0:
                logger.debug("OpenRouter cache is fresh, skipping sync")
                return 0
        
        # Fetch fresh models
        models = await self.fetch_available_models()
        if not models:
            return 0
        
        # Upsert to cache
        cache_entries = [
            {
                'model_id': model['id'],
                'model_data': model,
                'fetched_at': 'NOW()',
                'is_stale': False
            }
            for model in models
        ]
        
        await client.table('openrouter_model_cache')\
            .upsert(cache_entries)\
            .execute()
        
        logger.info(f"Synced {len(models)} models to cache")
        return len(models)
    
    async def get_cached_models(self, include_stale: bool = False) -> List[Dict]:
        """Get models from cache"""
        db = DBConnection()
        client = await db.client
        
        query = client.table('openrouter_model_cache').select('*')
        
        if not include_stale:
            query = query.eq('is_stale', False)
        
        result = await query.order('model_id').execute()
        return [row['model_data'] for row in result.data] if result.data else []

# Singleton instance
openrouter_sync = OpenRouterSync() if config.OPENROUTER_API_KEY else None
```

---

### 3. Admin API Endpoints

**File:** `backend/core/admin/model_admin_api.py`

```python
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from core.auth import require_super_admin
from core.services.supabase import DBConnection
from core.ai_models.openrouter_sync import openrouter_sync
from core.utils.logger import logger

router = APIRouter(prefix="/admin/models", tags=["admin-models"])

class ModelConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    is_recommended: Optional[bool] = None
    priority: Optional[int] = None
    tier_availability: Optional[List[str]] = None
    custom_params: Optional[Dict[str, Any]] = None
    custom_pricing: Optional[Dict[str, float]] = None

# ====================
# OPENROUTER MODEL DISCOVERY
# ====================

@router.get("/openrouter/available")
async def list_openrouter_models(
    refresh: bool = False,
    admin: dict = Depends(require_super_admin)
) -> Dict[str, Any]:
    """
    Get all available models from OpenRouter.
    Super admin only.
    
    Args:
        refresh: If true, force refresh from OpenRouter API
    """
    try:
        if not openrouter_sync:
            raise HTTPException(
                status_code=503,
                detail="OpenRouter not configured. Add OPENROUTER_API_KEY to environment."
            )
        
        if refresh:
            synced_count = await openrouter_sync.sync_to_cache(force=True)
            logger.info(f"[ADMIN] Force refreshed {synced_count} models from OpenRouter")
        
        models = await openrouter_sync.get_cached_models()
        
        return {
            "total": len(models),
            "models": models,
            "cache_fresh": not refresh
        }
        
    except Exception as e:
        logger.error(f"Error listing OpenRouter models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/openrouter/sync")
async def sync_openrouter_models(
    admin: dict = Depends(require_super_admin)
) -> Dict[str, Any]:
    """
    Manually trigger sync of models from OpenRouter API.
    Super admin only.
    """
    try:
        if not openrouter_sync:
            raise HTTPException(status_code=503, detail="OpenRouter not configured")
        
        synced_count = await openrouter_sync.sync_to_cache(force=True)
        
        return {
            "success": True,
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} models from OpenRouter"
        }
        
    except Exception as e:
        logger.error(f"Error syncing OpenRouter models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================
# MODEL CONFIGURATION MANAGEMENT
# ====================

@router.get("/configured")
async def list_configured_models(
    enabled_only: bool = False,
    admin: dict = Depends(require_super_admin)
) -> List[Dict]:
    """
    Get all configured models from database.
    Super admin only.
    """
    try:
        db = DBConnection()
        client = await db.client
        
        query = client.table('model_configurations').select('*')
        
        if enabled_only:
            query = query.eq('is_enabled', True)
        
        result = await query.order('priority', desc=True).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"Error listing configured models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{model_id}/configure")
async def configure_model(
    model_id: str,
    config: ModelConfigUpdate,
    admin: dict = Depends(require_super_admin)
) -> Dict:
    """
    Enable/configure a model for use.
    Super admin only.
    """
    try:
        db = DBConnection()
        client = await db.client
        
        # Build update data
        update_data = {
            'model_id': model_id,
            'modified_by': admin['user_id'],
            'updated_at': 'NOW()'
        }
        
        if config.is_enabled is not None:
            update_data['is_enabled'] = config.is_enabled
        if config.is_recommended is not None:
            update_data['is_recommended'] = config.is_recommended
        if config.priority is not None:
            update_data['priority'] = config.priority
        if config.tier_availability is not None:
            update_data['tier_availability'] = config.tier_availability
        if config.custom_params is not None:
            update_data['custom_params'] = config.custom_params
        if config.custom_pricing is not None:
            update_data['custom_pricing'] = config.custom_pricing
        
        # Upsert configuration
        result = await client.table('model_configurations')\
            .upsert(update_data)\
            .execute()
        
        logger.info(f"[ADMIN] {admin['user_id']} configured model {model_id}")
        
        return {
            "success": True,
            "model_id": model_id,
            "configuration": result.data[0] if result.data else None
        }
        
    except Exception as e:
        logger.error(f"Error configuring model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{model_id}")
async def disable_model(
    model_id: str,
    admin: dict = Depends(require_super_admin)
) -> Dict:
    """
    Disable a model (soft delete - keeps config).
    Super admin only.
    """
    try:
        db = DBConnection()
        client = await db.client
        
        result = await client.table('model_configurations')\
            .update({
                'is_enabled': False,
                'modified_by': admin['user_id'],
                'updated_at': 'NOW()'
            })\
            .eq('model_id', model_id)\
            .execute()
        
        logger.info(f"[ADMIN] {admin['user_id']} disabled model {model_id}")
        
        return {
            "success": True,
            "model_id": model_id,
            "message": "Model disabled"
        }
        
    except Exception as e:
        logger.error(f"Error disabling model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 4. Modified Model Manager

**File:** `backend/core/ai_models/manager.py` (additions)

```python
async def list_available_models_dynamic(
    self,
    tier: Optional[str] = None,
    include_disabled: bool = False
) -> List[Dict[str, Any]]:
    """
    List models from database configuration instead of hardcoded registry.
    Falls back to registry if database is empty.
    """
    try:
        db = DBConnection()
        client = await db.client
        
        # Try to get models from database configuration
        query = client.table('model_configurations').select('*')
        
        if not include_disabled:
            query = query.eq('is_enabled', True)
        
        if tier:
            query = query.contains('tier_availability', [tier])
        
        result = await query.order('priority', desc=True).execute()
        
        if result.data and len(result.data) > 0:
            # Use database configuration
            logger.debug(f"Using {len(result.data)} models from database config")
            return [self._db_config_to_model_dict(cfg) for cfg in result.data]
        else:
            # Fall back to hardcoded registry
            logger.debug("No database models found, using hardcoded registry")
            return self.list_available_models(tier, include_disabled)
            
    except Exception as e:
        logger.error(f"Error getting dynamic models: {e}, falling back to registry")
        return self.list_available_models(tier, include_disabled)

def _db_config_to_model_dict(self, config: Dict) -> Dict[str, Any]:
    """Convert database model config to model dict"""
    return {
        "id": config['model_id'],
        "name": config.get('display_name', config['model_id']),
        "provider": config['provider'],
        "context_window": config.get('context_window', 128000),
        "capabilities": config.get('capabilities', ['chat']),
        "pricing": config.get('custom_pricing'),
        "enabled": config['is_enabled'],
        "tier_availability": config.get('tier_availability', ['paid']),
        "priority": config.get('priority', 50),
        "recommended": config.get('is_recommended', False),
        "custom_params": config.get('custom_params', {})
    }
```

---

### 5. Frontend Admin Page

**File:** `frontend/src/app/(dashboard)/admin/models/page.tsx`

```tsx
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { backendApi } from '@/lib/backend-api';
import { Loader2, RefreshCw, Settings, CheckCircle, XCircle } from 'lucide-react';

export default function AdminModelsPage() {
  const queryClient = useQueryClient();
  const [selectedModel, setSelectedModel] = useState<string | null>(null);

  // Fetch OpenRouter models
  const { data: openrouterModels, isLoading: loadingOpenRouter } = useQuery({
    queryKey: ['admin', 'openrouter-models'],
    queryFn: async () => {
      const response = await backendApi.get('/admin/models/openrouter/available');
      return response.data;
    }
  });

  // Fetch configured models
  const { data: configuredModels, isLoading: loadingConfigured } = useQuery({
    queryKey: ['admin', 'configured-models'],
    queryFn: async () => {
      const response = await backendApi.get('/admin/models/configured');
      return response.data;
    }
  });

  // Sync from OpenRouter
  const syncMutation = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post('/admin/models/openrouter/sync');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'openrouter-models'] });
    }
  });

  // Enable/disable model
  const configureMutation = useMutation({
    mutationFn: async ({ modelId, isEnabled }: { modelId: string, isEnabled: boolean }) => {
      const response = await backendApi.post(`/admin/models/${modelId}/configure`, {
        is_enabled: isEnabled
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'configured-models'] });
    }
  });

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Model Management</h1>
          <p className="text-muted-foreground">
            Configure AI models available to users (Super Admin Only)
          </p>
        </div>
        
        <Button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
        >
          {syncMutation.isPending ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Syncing...</>
          ) : (
            <><RefreshCw className="mr-2 h-4 w-4" /> Sync from OpenRouter</>
          )}
        </Button>
      </div>

      {/* Available OpenRouter Models */}
      <Card>
        <CardHeader>
          <CardTitle>Available Models (OpenRouter)</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingOpenRouter ? (
            <div className="flex justify-center p-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {openrouterModels?.models?.slice(0, 20).map((model: any) => (
                <div
                  key={model.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex-1">
                    <div className="font-medium">{model.name}</div>
                    <div className="text-sm text-muted-foreground">{model.id}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Context: {model.context_length?.toLocaleString()} tokens
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-4">
                    {model.pricing && (
                      <div className="text-sm text-right">
                        <div>${(model.pricing.prompt * 1_000_000).toFixed(2)}/M in</div>
                        <div>${(model.pricing.completion * 1_000_000).toFixed(2)}/M out</div>
                      </div>
                    )}
                    
                    <Switch
                      checked={configuredModels?.some((c: any) => 
                        c.model_id === model.id && c.is_enabled
                      )}
                      onCheckedChange={(checked) => 
                        configureMutation.mutate({ modelId: model.id, isEnabled: checked })
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Currently Enabled Models */}
      <Card>
        <CardHeader>
          <CardTitle>Enabled Models</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingConfigured ? (
            <div className="flex justify-center p-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : configuredModels?.filter((m: any) => m.is_enabled).length === 0 ? (
            <p className="text-muted-foreground text-center p-8">
              No models enabled yet. Enable models from the list above.
            </p>
          ) : (
            <div className="space-y-2">
              {configuredModels
                ?.filter((m: any) => m.is_enabled)
                .map((model: any) => (
                  <div
                    key={model.model_id}
                    className="flex items-center justify-between p-4 border rounded-lg bg-muted/50"
                  >
                    <div>
                      <div className="font-medium">{model.display_name || model.model_id}</div>
                      <div className="text-sm text-muted-foreground">{model.model_id}</div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {model.is_recommended && (
                        <Badge variant="default">Recommended</Badge>
                      )}
                      <Badge variant="outline">Priority: {model.priority}</Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedModel(model.model_id)}
                      >
                        <Settings className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

---

### 6. Migration File

**File:** `backend/supabase/migrations/20251117220000_model_management.sql`

```sql
-- Model Management System for Superadmin
-- Date: 2025-11-17

BEGIN;

-- Create model_configurations table
CREATE TABLE IF NOT EXISTS public.model_configurations (
    model_id VARCHAR PRIMARY KEY,
    provider VARCHAR NOT NULL,
    is_enabled BOOLEAN DEFAULT false,
    is_recommended BOOLEAN DEFAULT false,
    priority INT DEFAULT 50,
    tier_availability VARCHAR[] DEFAULT ARRAY['paid'],
    custom_params JSONB DEFAULT '{}',
    custom_pricing JSONB DEFAULT NULL,
    display_name VARCHAR,
    description TEXT,
    context_window INT,
    capabilities VARCHAR[] DEFAULT ARRAY[]::VARCHAR[],
    created_by UUID REFERENCES auth.users(id),
    modified_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_model_configs_enabled ON public.model_configurations(is_enabled, priority DESC);
CREATE INDEX idx_model_configs_provider ON public.model_configurations(provider);

ALTER TABLE public.model_configurations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view enabled models" ON public.model_configurations
    FOR SELECT USING (is_enabled = true);

CREATE POLICY "Only super_admin can manage models" ON public.model_configurations
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.user_roles
            WHERE user_id = auth.uid()
            AND role = 'super_admin'
        )
    );

CREATE POLICY "Service role manages models" ON public.model_configurations
    FOR ALL USING (auth.role() = 'service_role');

-- Create OpenRouter cache table
CREATE TABLE IF NOT EXISTS public.openrouter_model_cache (
    model_id VARCHAR PRIMARY KEY,
    model_data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT false
);

CREATE INDEX idx_openrouter_cache_stale ON public.openrouter_model_cache(fetched_at DESC);

-- Insert default GPT-5.1 Chat as enabled
INSERT INTO public.model_configurations (
    model_id,
    provider,
    is_enabled,
    is_recommended,
    priority,
    tier_availability,
    display_name,
    context_window,
    capabilities
) VALUES (
    'openai/gpt-5.1-chat',
    'openrouter',
    true,
    true,
    105,
    ARRAY['paid'],
    'GPT-5.1 Chat',
    256000,
    ARRAY['chat', 'function_calling', 'vision', 'thinking']
) ON CONFLICT (model_id) DO NOTHING;

COMMIT;
```

---

## Implementation Timeline

**Phase 1: Database (30 min)**
- Create migration file
- Apply to Supabase
- Verify tables created

**Phase 2: Backend Service (1 hour)**
- Create `openrouter_sync.py`
- Create `model_admin_api.py`
- Wire into main API

**Phase 3: Frontend UI (2 hours)**
- Create admin models page
- Add to admin navigation
- Test enable/disable flow

**Phase 4: Integration (1 hour)**
- Modify `model_manager.py` to check DB first
- Add cron job for auto-sync
- Test end-to-end

---

## Benefits

✅ **Superadmin controls models** via UI (not code)  
✅ **Auto-discover new models** from OpenRouter  
✅ **Per-model parameters** (temp, max_tokens, etc.)  
✅ **Audit trail** (who enabled what, when)  
✅ **No redeploy needed** for model changes  
✅ **Future-proof** for multi-provider support  

---

## Testing Checklist

- [ ] Superadmin can see OpenRouter models list
- [ ] Superadmin can enable/disable models
- [ ] Enabled models appear in user model picker
- [ ] Disabled models don't appear for users
- [ ] Custom parameters are applied to LiteLLM calls
- [ ] Non-superadmin users cannot access admin endpoints
- [ ] Cache refreshes every hour automatically

---

**Ready to implement when you are!**

