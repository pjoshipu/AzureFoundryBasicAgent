import os
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

credential = ClientSecretCredential(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
)

project_client = AIProjectClient(
    endpoint=os.getenv("AZURE_ENDPOINT"),
    credential=credential,
)

agent_name = "AzureFoundryAgent"
model_deployment_name = os.getenv("MODEL_DEPLOYMENT_NAME")

# Creates an agent, bumps the agent version if parameters have changed
agent = project_client.agents.create_version(  
    agent_name=agent_name,
    definition=PromptAgentDefinition(
            model=model_deployment_name,
            instructions="You are a storytelling agent. You craft engaging one-line stories based on user prompts and context.",
        ),
)

openai_client = project_client.get_openai_client()

# Reference the agent to get a response
response = openai_client.responses.create(
    input=[{"role": "user", "content": "Tell me a one line story"}],
    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
)

print(f"Response output: {response.output_text}")
