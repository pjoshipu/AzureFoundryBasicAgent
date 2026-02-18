# Step 6: Test UI for the hosted Azure Functions agent
# This Gradio app lets you test the agent running via `func start`
import json
import traceback
from pathlib import Path

import gradio as gr
import requests

DEFAULT_BASE_URL = "http://localhost:7071"
AGENT_NAME = "HostedAgent"


# ---------------------------------------------------------------------------
# Call the hosted agent endpoint
# ---------------------------------------------------------------------------
def call_agent(user_prompt, base_url):
    try:
        url = f"{base_url.rstrip('/')}/api/agents/{AGENT_NAME}/run"

        resp = requests.post(
            url,
            headers={"Content-Type": "text/plain"},
            data=user_prompt,
            timeout=30,
        )

        if resp.status_code == 200:
            return resp.text, f"Status: {resp.status_code} OK"
        elif resp.status_code == 202:
            # Async — poll for result
            body = resp.json()
            detail = json.dumps(body, indent=2)
            return f"Accepted (async). Response:\n{detail}", f"Status: {resp.status_code} Accepted"
        else:
            return f"HTTP {resp.status_code}: {resp.text}", f"Status: {resp.status_code}"

    except requests.ConnectionError:
        return (
            "Connection refused. Is the Functions host running?\n\n"
            "Start it with:\n  cd step6_hosting && func start",
            "Status: Connection Error",
        )
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}", "Status: Error"


def check_health(base_url):
    try:
        url = f"{base_url.rstrip('/')}/api/health"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"Healthy (HTTP {resp.status_code})"
        return f"HTTP {resp.status_code}: {resp.text}"
    except requests.ConnectionError:
        return "Not reachable — is `func start` running?"
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

SAMPLE_PROMPTS = [
    "Tell me a short joke about cloud computing.",
    "What is serverless computing in one sentence?",
    "Explain Azure Functions in simple terms.",
]

with gr.Blocks(title="Step 6: Host Your Agent") as app:
    gr.Markdown("# Step 6: Host Your Agent")
    gr.Markdown(
        "This UI tests your agent hosted via **Azure Functions**. "
        "The agent is registered with `AgentFunctionApp` in `function_app.py`."
    )

    with gr.Tab("Test Agent"):
        gr.Markdown("### Setup")
        gr.Markdown(
            "1. Install [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)\n"
            "2. Start the host: `cd step6_hosting && func start`\n"
            "3. Use this UI to send requests to the agent endpoint"
        )

        base_url = gr.Textbox(
            label="Functions Base URL",
            value=DEFAULT_BASE_URL,
            interactive=True,
        )

        with gr.Row():
            health_btn = gr.Button("Check Health", variant="secondary")
            health_output = gr.Textbox(label="Health Status", interactive=False)

        health_btn.click(fn=check_health, inputs=base_url, outputs=health_output)

        gr.Markdown("---")
        gr.Markdown("### Send a request")
        gr.Markdown(f"**Endpoint:** `POST /api/agents/{AGENT_NAME}/run`")

        with gr.Row():
            example_btns = []
            for prompt_text in SAMPLE_PROMPTS:
                example_btns.append(gr.Button(prompt_text, size="sm", variant="secondary"))

        user_prompt = gr.Textbox(
            label="Your Prompt",
            placeholder="Type a message to send to the hosted agent...",
            lines=2,
        )

        for btn in example_btns:
            btn.click(fn=lambda t=btn.value: t, outputs=user_prompt)

        send_btn = gr.Button("Send", variant="primary")
        response_output = gr.Textbox(label="Agent Response", interactive=False, lines=4)
        status_output = gr.Textbox(label="HTTP Status", interactive=False)

        send_btn.click(
            fn=call_agent,
            inputs=[user_prompt, base_url],
            outputs=[response_output, status_output],
        )

    with gr.Tab("function_app.py"):
        gr.Markdown("### Agent Registration Code")
        func_app_path = Path(__file__).parent / "function_app.py"
        func_app_code = func_app_path.read_text(encoding="utf-8") if func_app_path.exists() else "Not found."
        gr.Code(value=func_app_code, language="python", label="function_app.py")

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
