import os
import sys
from pathlib import Path

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from azure.ai.projects.models import PromptAgentDefinition
from shared import get_project_client, get_openai_client

project_client = get_project_client()
openai_client = get_openai_client()

AGENT_NAME = "AzureFoundryAgent"
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
RESPONSE_CONSTRAINT = 'Keep your response "one-line" only.'


def send_message(user_prompt):
    instructions = f"You are a helpful agent.\n\n{RESPONSE_CONSTRAINT}"

    agent = project_client.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=MODEL_DEPLOYMENT_NAME,
            instructions=instructions,
        ),
    )

    response = openai_client.responses.create(
        input=[{"role": "user", "content": user_prompt}],
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
    )

    return response.output_text


# Load setup guide markdown
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

with gr.Blocks(title="Step 1: Basic Agent") as app:
    gr.Markdown("# Step 1: Basic Azure Foundry Agent")

    with gr.Tab("Agent"):
        constraint = gr.Textbox(
            label="Response Constraint",
            value=RESPONSE_CONSTRAINT,
            interactive=False,
        )
        user_prompt = gr.Textbox(
            label="Your Prompt",
            placeholder="e.g., Tell me a one line story",
            lines=2,
        )
        send_btn = gr.Button("Send", variant="primary")
        response_output = gr.Textbox(
            label="Response",
            interactive=False,
        )
        send_btn.click(
            fn=send_message,
            inputs=user_prompt,
            outputs=response_output,
        )

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
