import os
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.ai.projects import AIProjectClient

load_dotenv()


def get_credential():
    return ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    )


def get_project_client():
    return AIProjectClient(
        endpoint=os.getenv("AZURE_ENDPOINT"),
        credential=get_credential(),
    )


def get_openai_client():
    return get_project_client().get_openai_client()
