import os
import sys
import json
import traceback
from pathlib import Path

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from shared import get_openai_client

openai_client = get_openai_client()

AGENT_NAME = "AzureFoundryAgent"
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")

# ---------------------------------------------------------------------------
# Load data from JSON files
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"

with open(DATA_DIR / "tool_definitions.json") as f:
    TOOL_DEFINITIONS = json.load(f)

with open(DATA_DIR / "weather.json") as f:
    WEATHER_DATA = json.load(f)

with open(DATA_DIR / "products.json") as f:
    PRODUCT_DB = json.load(f)

with open(DATA_DIR / "knowledge_base.json") as f:
    KNOWLEDGE_BASE = json.load(f)

with open(DATA_DIR / "sample_prompts.json") as f:
    SAMPLE_PROMPTS = json.load(f)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def get_weather(city: str) -> str:
    data = WEATHER_DATA.get(city.lower())
    if data:
        return json.dumps({"city": city.title(), **data})
    return json.dumps({"city": city.title(), "temp": "N/A", "condition": "Data not available",
                        "note": "City not in demo dataset"})


def query_products(category: str, max_price: float = None) -> str:
    products = PRODUCT_DB.get(category.lower(), [])
    if not products:
        return json.dumps({"category": category, "results": [],
                            "note": "Category not found. Available: electronics, books, clothing"})
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    return json.dumps({"category": category, "result_count": len(products), "products": products})


def search_knowledge_base(query: str) -> str:
    query_lower = query.lower()
    matches = []
    for key, content in KNOWLEDGE_BASE.items():
        if key in query_lower or any(word in query_lower for word in key.split()):
            matches.append({"topic": key, "content": content})
    if not matches:
        return json.dumps({"query": query, "results": [],
                            "note": "No matching articles. Try: return, shipping, warranty, hours, payment"})
    return json.dumps({"query": query, "result_count": len(matches), "results": matches})


TOOL_FUNCTIONS = {
    "get_weather": lambda args: get_weather(**args),
    "query_products": lambda args: query_products(**args),
    "search_knowledge_base": lambda args: search_knowledge_base(**args),
}

# ---------------------------------------------------------------------------
# Agent logic with tool-calling loop
# ---------------------------------------------------------------------------
def send_message(user_prompt):
    try:
        instructions = (
            "You are a helpful assistant with access to tools.\n"
            "Use the available tools to answer the user's questions accurately.\n"
            "When you use a tool, explain what you found in a clear, friendly way."
        )

        tool_log = []

        # Note: Azure Foundry agent references do not support the `tools` param.
        # So we call the model directly with tools via the standard Responses API.
        response = openai_client.responses.create(
            model=MODEL_DEPLOYMENT_NAME,
            instructions=instructions,
            input=[{"role": "user", "content": user_prompt}],
            tools=TOOL_DEFINITIONS,
        )

        # Tool-calling loop
        for _ in range(5):
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                break

            tool_results = []
            for fc in function_calls:
                args = json.loads(fc.arguments)
                tool_fn = TOOL_FUNCTIONS.get(fc.name)
                result = tool_fn(args) if tool_fn else json.dumps({"error": f"Unknown tool: {fc.name}"})

                tool_log.append({"tool": fc.name, "input": args, "output": json.loads(result)})
                tool_results.append({
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": result,
                })

            response = openai_client.responses.create(
                model=MODEL_DEPLOYMENT_NAME,
                input=tool_results,
                previous_response_id=response.id,
                tools=TOOL_DEFINITIONS,
            )

        tool_log_text = json.dumps(tool_log, indent=2) if tool_log else ""
        return response.output_text, tool_log_text

    except Exception as e:
        error_msg = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        return error_msg, ""


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

with gr.Blocks(title="Step 2: Agent with Tools", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Step 2: Azure Foundry Agent with Tools")
    gr.Markdown(
        "This agent can **call tools** to fetch real data before responding. "
        "It decides which tool to use based on your question."
    )

    with gr.Tab("Agent"):
        gr.Markdown("### Available Tools")
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown(
                    "**`get_weather`**\n\n"
                    "Fetches current weather data for a city.\n\n"
                    "*Simulates an external API call.*"
                )
            with gr.Column(scale=1):
                gr.Markdown(
                    "**`query_products`**\n\n"
                    "Queries product database by category & price.\n\n"
                    "*Simulates a database query.*"
                )
            with gr.Column(scale=1):
                gr.Markdown(
                    "**`search_knowledge_base`**\n\n"
                    "Searches company docs & FAQs.\n\n"
                    "*Simulates a knowledge base / search API.*"
                )

        gr.Markdown("---")
        gr.Markdown("### Try it out")

        with gr.Row():
            example_btns = []
            for prompt_text in SAMPLE_PROMPTS:
                example_btns.append(gr.Button(prompt_text, size="sm", variant="secondary"))

        user_prompt = gr.Textbox(
            label="Your Prompt",
            placeholder="Ask about weather, products, or company policies...",
            lines=2,
        )

        for btn in example_btns:
            btn.click(fn=lambda t=btn.value: t, outputs=user_prompt)

        send_btn = gr.Button("Send", variant="primary")
        response_output = gr.Textbox(label="Agent Response", interactive=False, lines=4)

        with gr.Accordion("Tool Call Log", open=False):
            gr.Markdown("*Shows which tools the agent called, the inputs it chose, and the raw data returned.*")
            tool_log_output = gr.Code(label="Tool Calls (JSON)", language="json")

        send_btn.click(
            fn=send_message,
            inputs=user_prompt,
            outputs=[response_output, tool_log_output],
        )

    with gr.Tab("Tool Definitions"):
        gr.Markdown("### Function Schemas sent to the Agent")
        gr.Markdown(
            "These JSON schemas tell the agent what tools are available, "
            "what parameters they accept, and when to use them."
        )
        gr.Code(
            value=json.dumps(TOOL_DEFINITIONS, indent=2),
            language="json",
            label="Tool Definitions",
        )

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
