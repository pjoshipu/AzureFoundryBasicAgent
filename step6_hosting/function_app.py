# Step 6: Host Your Agent with Azure Functions
# Run with: func start
# Test with: curl -X POST http://localhost:7071/api/agents/HostedAgent/run \
#              -H "Content-Type: text/plain" \
#              -d "Tell me a joke about cloud computing."

import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_framework.azure import AgentFunctionApp, AzureOpenAIResponsesClient
from shared import get_credential

MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
PROJECT_ENDPOINT = os.getenv("AZURE_ENDPOINT")


# ---------------------------------------------------------------------------
# 1. Create the agent
# ---------------------------------------------------------------------------
def _create_agent() -> Any:
    """Create the hosted agent backed by Azure OpenAI Responses API."""
    client = AzureOpenAIResponsesClient(
        project_endpoint=PROJECT_ENDPOINT,
        deployment_name=MODEL_DEPLOYMENT_NAME,
        credential=get_credential(),
    )
    return client.as_agent(
        name="HostedAgent",
        instructions=(
            "You are a helpful, friendly assistant hosted in Azure Functions. "
            "Keep your answers concise and useful."
        ),
    )


# ---------------------------------------------------------------------------
# 2. Register the agent with AgentFunctionApp
# ---------------------------------------------------------------------------
app = AgentFunctionApp(
    agents=[_create_agent()],
    enable_health_check=True,
    max_poll_retries=50,
)
