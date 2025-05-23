# Project Overview

This document provides an end‑to‑end description of the repository structure, the main components and how they interact. It also lists every location where the sandbox provider is referenced and outlines a plan to swap the default Daytona implementation with a self‑hosted alternative such as e2b or CodeSandbox.

## Repository Layout

```
.
├── backend/             # FastAPI service and background worker
│   ├── agent/           # Agent execution logic and tools
│   ├── agentpress/      # Higher level abstractions for tools and threads
│   ├── sandbox/         # Sandbox management code
│   ├── services/        # Supabase, Redis, billing, LLM helpers
│   ├── utils/           # Utility modules and scripts
│   ├── pyproject.toml   # Python dependencies
│   └── requirements.txt
├── docs/                # Documentation
├── frontend/            # Next.js client
├── docker-compose.yaml  # Container orchestration
├── setup.py             # Interactive setup wizard
└── start.py             # Helper to start/stop Docker compose
```

### Key Components

- **backend/api.py** – Starts the FastAPI application, registers routes and initialises services.
- **backend/run_agent_background.py** – Dramatiq worker that processes queued agent tasks.
- **backend/agent/** – Contains `run.py` (agent orchestrator), prompt templates and multiple `tools` used by the agent.
- **backend/sandbox/** – Manages the remote execution environment. `sandbox.py` wraps the `daytona_sdk` client. `tool_base.py` provides sandbox access for agent tools.
- **backend/services/** – Modules for Supabase (`supabase.py`), Redis (`redis.py`), LLM providers (`llm.py`) and billing (`billing.py`).
- **backend/utils/config.py** – Loads environment variables (Supabase, LLM, sandbox provider settings, etc.) and validates configuration.
- **backend/utils/scripts/** – Maintenance scripts such as `archive_old_sandboxes.py` and `delete_user_sandboxes.py` that operate on sandboxes.
- **frontend/** – Next.js application. Communicates with the backend via REST APIs.
- **setup.py** – Wizard that checks prerequisites, prompts for credentials (Supabase, sandbox provider, LLMs) and writes `.env` files used by the backend and frontend.

## Sandbox Provider Integration Points

The sandbox provider is referenced in a number of files. By default this is Daytona:

- Environment variables in `backend/.env.example`:
  ```
  DAYTONA_API_KEY=
  DAYTONA_SERVER_URL=
  DAYTONA_TARGET=
  ```
- Configuration fields in `backend/utils/config.py` that load these variables.
- `setup.py` function `collect_daytona_info()` prompts for the Daytona API key and image information (to be replaced with provider-neutral prompts).
- `backend/sandbox/sandbox.py` imports `daytona_sdk` and manages sandbox creation/start (`Daytona`, `CreateSandboxParams`, etc.).
- Agent tools under `backend/agent/tools` rely on `SandboxToolsBase`, which in turn calls `get_or_start_sandbox` from `sandbox/sandbox.py`.
- Utility scripts in `backend/utils/scripts/` import `daytona` from `sandbox.sandbox` to archive or delete sandboxes.
- Documentation mentions Daytona in `README.md` and `docs/SELF-HOSTING.md`.
- Daytona is included as a dependency in `backend/pyproject.toml` and `backend/requirements.txt`.

## How Components Interact

1. **Setup and Configuration** – Running `python setup.py` collects all required credentials. It writes `.env` files used by the backend (`backend/.env`) and frontend (`frontend/.env.local`). The backend loads these values through `utils/config.py`.
2. **Starting the Platform** – `start.py` (or `docker compose up`) launches the backend API, worker, Redis, RabbitMQ and the frontend.
3. **Agent Execution** – Client requests hit the FastAPI API. Tasks are queued to the worker (`run_agent_background.py`) which uses modules from `agent/` and `agentpress/` to execute tools in a sandbox.
4. **Sandbox Lifecycle** – `backend/sandbox/sandbox.py` uses the Daytona client to create or resume a sandbox. Agent tools call `get_or_start_sandbox` via `SandboxToolsBase` to ensure a sandbox exists for the project.
5. **Persistence** – Supabase stores user data and project metadata. Redis caches sessions. The sandbox ID/password are stored in the `projects` table so tools can reconnect later.

## Replacing Daytona

To self‑host the sandbox component, the Daytona specific code can be abstracted behind a provider interface. The steps below outline this approach.

1. **Provider Interface**
   - Create a module `sandbox/provider_base.py` defining an abstract `SandboxProvider` with methods like `create_sandbox`, `start_sandbox`, `execute_command`, `upload_file`, `download_file` and `delete_sandbox`.
   - Refactor `sandbox/sandbox.py` into `DaytonaProvider` implementing this interface.

2. **Implement a Self‑Hosted Provider**
   - Add a new module (`e2b_provider.py` or `codesandbox_provider.py`) that uses the chosen provider’s API to perform the same operations.
   - Include the provider’s dependency in `backend/pyproject.toml`/`requirements.txt`.
   - Allow selection via an environment variable, e.g. `SANDBOX_PROVIDER=daytona|e2b`.

3. **Update Tools**
   - Modify `SandboxToolsBase` to use the provider interface rather than importing `daytona_sdk`. All calls to `daytona.*` methods should be routed through the provider abstraction.

4. **Revise Configuration and Setup**
   - Replace `DAYTONA_*` variables with provider-neutral names (`SANDBOX_API_KEY`, `SANDBOX_SERVER_URL`, etc.) in `config.py` and `.env.example`.
   - Update `setup.py` to prompt for the new provider and credentials (replace `collect_daytona_info`).

5. **Adjust Scripts and Documentation**
   - Update maintenance scripts in `backend/utils/scripts/` to use the provider interface.
   - Rewrite mentions of Daytona in `README.md` and `docs/SELF-HOSTING.md` to describe the new provider.

6. **Data Migration**
   - If sandbox IDs are stored in Supabase, write a migration script to create equivalent sandboxes in the new system and update the database records.

7. **Testing and Rollout**
   - Validate that the new provider supports concurrent sandbox sessions for thousands of users.
   - Run load tests and ensure all agent tools (browser, shell, file operations) function correctly.
   - Once confirmed, switch the production configuration to the new provider and remove Daytona dependencies.

---

This overview should serve as a starting point for contributors to understand how the project pieces fit together and how Daytona is currently integrated. Following the plan above will decouple the sandbox logic from Daytona and allow using a self‑hosted alternative.
