# Developer Guide

This guide explains how the Suna codebase is organized and how the main modules interact. It also outlines where the sandbox provider is integrated so contributors can replace Daytona with an open‑source alternative if desired.

## Directory Overview

- **backend/** – FastAPI service, agent logic and helper modules.
- **backend/agent/** – Orchestrates agent runs and contains tools executed inside a sandbox.
- **backend/agentpress/** – Higher‑level abstractions for conversation threads and tool invocation.
- **backend/sandbox/** – Abstraction layer for sandbox providers.
- **backend/sandbox/providers/** – Implementations for specific providers (Daytona by default).
- **backend/services/** – Database (Supabase), Redis and LLM helper modules.
- **backend/utils/** – Configuration loader, logging and maintenance scripts.
- **frontend/** – Next.js interface communicating with the backend API.
- **docs/** – Project documentation.
- **setup.py** – Interactive setup wizard creating environment files.
- **start.py** – Convenience script for running `docker compose`.

## Key Relationships

1. **Configuration** (`backend/utils/config.py`)
   - Loads environment variables and exposes them via the `config` singleton.
   - Contains sandbox provider settings (`SANDBOX_PROVIDER`, `SANDBOX_API_KEY`, etc.).

2. **Sandbox Management** (`backend/sandbox`)
   - `sandbox/sandbox.py` selects a provider implementation (Daytona or others) and exposes `get_or_start_sandbox` and `create_sandbox` helpers.
   - Providers live in `sandbox/providers/`. `daytona_provider.py` wraps `daytona_sdk`. `e2b_provider.py` is a stub for future integration.
   - Agent tools inherit from `SandboxToolsBase` which retrieves the project sandbox using these helpers.

3. **Agent Execution**
   - Requests come through `backend/api.py`. Heavy work happens in `run_agent_background.py` via Dramatiq.
   - Tools under `backend/agent/tools` rely on `SandboxToolsBase` for shell commands, browser automation and file access inside the sandbox.

4. **Frontend**
   - Located in `frontend/`, this Next.js app calls backend routes to run agents and display results.

5. **Setup Wizard**
   - `setup.py` checks prerequisites and collects credentials for Supabase, the sandbox provider and LLM APIs.
   - It writes `.env` files for the backend and frontend using the collected information.

## Daytona Integration Points

The following locations interact directly with the Daytona SDK and will need adjustments when switching providers:

- Environment variables in `backend/.env.example`.
- Provider configuration in `backend/utils/config.py`.
- Sandbox logic in `backend/sandbox/providers/daytona_provider.py`.
- Utility scripts in `backend/utils/scripts/*` import `daytona` from the sandbox module.
- The setup wizard uses `collect_daytona_info()` when Daytona is selected.

## Swapping Providers

1. Implement a new provider in `backend/sandbox/providers/` following the `SandboxProvider` interface.
2. Update `SANDBOX_PROVIDER` in your `.env` to select the provider.
3. Adjust `setup.py` to prompt for the new provider’s credentials.
4. Update documentation to describe how to run the chosen provider.

With this structure, the rest of the agent code remains unchanged while allowing different sandbox backends.

