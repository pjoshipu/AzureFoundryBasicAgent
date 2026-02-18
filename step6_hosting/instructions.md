# Step 6: Host Your Agent with Azure Functions

## What this step does

Deploys your agent as an **HTTP endpoint** using Azure Functions so users and other agents can call it via a simple REST API.

## Architecture

```
Client (curl / Gradio UI / other agent)
  │
  POST /api/agents/HostedAgent/run
  │
  ▼
Azure Functions Host (func start)
  │
  AgentFunctionApp → AzureOpenAIResponsesClient → Azure OpenAI
```

## Files

| File | Purpose |
|------|---------|
| `function_app.py` | Agent creation + `AgentFunctionApp` registration |
| `host.json` | Azure Functions host configuration |
| `local.settings.json` | Local environment settings |
| `app.py` | Gradio test UI to call the hosted agent |

## Key code: `function_app.py`

### 1. Create the agent

```python
from agent_framework.azure import AgentFunctionApp, AzureOpenAIResponsesClient

def _create_agent():
    client = AzureOpenAIResponsesClient(
        project_endpoint=PROJECT_ENDPOINT,
        deployment_name=MODEL_DEPLOYMENT_NAME,
        credential=get_credential(),
    )
    return client.as_agent(
        name="HostedAgent",
        instructions="You are a helpful assistant hosted in Azure Functions.",
    )
```

### 2. Register with AgentFunctionApp

```python
app = AgentFunctionApp(
    agents=[_create_agent()],
    enable_health_check=True,
    max_poll_retries=50,
)
```

This single line exposes:
- `POST /api/agents/HostedAgent/run` — send a prompt, get a response
- `GET /api/health` — health check endpoint

## How to run locally

### Prerequisites

1. [Azure Functions Core Tools v4+](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
2. [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) (local storage emulator) — required by Durable Functions

### Install

```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
npm install -g azurite
```

### Run (two terminals)

**Terminal 1 — Start Azurite (storage emulator):**
```bash
azurite --silent
```

**Terminal 2 — Start the Functions host:**
```bash
cd step6_hosting

# If you have multiple Python versions, tell the py launcher to use 3.12
export PY_PYTHON=3.12    # bash
# or: set PY_PYTHON=3.12  (cmd)

func start
```

> **Note:** If `func start` picks up Python 3.13+ and fails with `ModuleNotFoundError: collections.abc`,
> set `PY_PYTHON=3.12` to force the correct Python version.

### Test with curl

```bash
curl -X POST http://localhost:7071/api/agents/HostedAgent/run \
  -H "Content-Type: text/plain" \
  -d "Tell me a joke about cloud computing."
```

### Test with the Gradio UI

```bash
# In a separate terminal
python app.py
```

The UI provides:
- Health check button to verify the Functions host is running
- Sample prompts to test the agent
- HTTP status display

## Reference

- [Agent Framework — Host Your Agent](https://learn.microsoft.com/en-us/agent-framework/get-started/hosting?pivots=programming-language-python)
- [Azure Functions hosting samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/azure_functions)
