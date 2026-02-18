# Step 4: Memory & Persistence using Context Providers
import asyncio
import os
import sys
import traceback
from typing import Any
from pathlib import Path

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework._sessions import AgentSession, BaseContextProvider, SessionContext, InMemoryHistoryProvider
from shared import get_credential

MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
PROJECT_ENDPOINT = os.getenv("AZURE_ENDPOINT")


# ---------------------------------------------------------------------------
# Context Provider — extracts and remembers user preferences
# ---------------------------------------------------------------------------
class UserPreferencesProvider(BaseContextProvider):
    """Remembers user details shared across the conversation."""

    def __init__(self) -> None:
        super().__init__(source_id="user-preferences-provider")
        self.facts: list[str] = []

    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        if self.facts:
            memory_block = "Known facts about the user:\n" + "\n".join(f"- {f}" for f in self.facts)
            context.instructions.append(memory_block)
            context.instructions.append(
                "Use these facts to personalize your response. "
                "When asked what you remember, start with 'Based on what I remember about you...' "
                "and list all known facts."
            )
        else:
            context.instructions.append(
                "You don't know anything about the user yet. "
                "Be friendly and encourage them to share about themselves."
            )

    async def after_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        for msg in context.input_messages:
            text = msg.text if hasattr(msg, "text") else ""
            if not isinstance(text, str):
                continue
            lower = text.lower()

            # Extract name
            if "my name is" in lower:
                name = lower.split("my name is")[-1].strip().split()[0].capitalize()
                fact = f"Name: {name}"
                if fact not in self.facts:
                    self.facts.append(fact)

            # Extract location
            if "from " in lower and ("live" in lower or "i'm from" in lower or "i am from" in lower):
                location = text.split("from")[-1].strip().rstrip(".,!").split(" and ")[0]
                fact = f"Location: {location}"
                if fact not in self.facts:
                    self.facts.append(fact)

            # Extract profession
            for keyword in ["i'm a ", "i am a ", "i work as ", "my job is "]:
                if keyword in lower:
                    profession = text.lower().split(keyword)[-1].strip().split(".")[0].split(",")[0].split(" and ")[0]
                    fact = f"Profession: {profession.title()}"
                    if fact not in self.facts:
                        self.facts.append(fact)

            # Extract hobbies / likes
            for keyword in ["i love ", "i like ", "i enjoy ", "my hobby is ", "my favorite "]:
                if keyword in lower:
                    interest = text.lower().split(keyword)[-1].strip().rstrip(".,!").split(" and ")[0]
                    fact = f"Interest: {interest.title()}"
                    if fact not in self.facts:
                        self.facts.append(fact)

    def get_memory_display(self) -> str:
        if not self.facts:
            return "No memories stored yet."
        return "\n".join(f"- {f}" for f in self.facts)


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------
credential = get_credential()
client = AzureOpenAIResponsesClient(
    project_endpoint=PROJECT_ENDPOINT,
    deployment_name=MODEL_DEPLOYMENT_NAME,
    credential=credential,
)

memory_provider = UserPreferencesProvider()
history_provider = InMemoryHistoryProvider("memory", load_messages=True)

agent = client.as_agent(
    name="MemoryAgent",
    instructions="You are a friendly, attentive assistant. Be warm and conversational.",
    context_providers=[memory_provider, history_provider],
)

agent_session = agent.create_session()


# ---------------------------------------------------------------------------
# Chat logic
# ---------------------------------------------------------------------------
def chat(user_message, history):
    try:
        result = asyncio.run(agent.run(user_message, session=agent_session))
        assistant_reply = str(result)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_reply})

        memory_display = memory_provider.get_memory_display()
        return history, "", memory_display

    except Exception as e:
        error = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": error})
        return history, "", memory_provider.get_memory_display()


def reset_session():
    global agent_session
    memory_provider.facts.clear()
    agent_session = agent.create_session()
    return [], "", "No memories stored yet."


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

STARTER_PROMPTS = [
    ["Hi! My name is Raj, I'm a cloud architect from Atlanta, Georgia."],
    ["I love barbecue and I enjoy hiking on weekends."],
    ["What do you remember about me?"],
]

with gr.Blocks(title="Step 4: Memory & Persistence", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Step 4: Memory & Persistence")
    gr.Markdown(
        "This agent uses a **Context Provider** to extract and remember user preferences "
        "across the conversation. The memory panel shows what the agent has stored."
    )

    with gr.Tab("Chat"):
        gr.Markdown("### How it works")
        gr.Markdown(
            "A `BaseContextProvider` hooks into every agent call:\n"
            "- **`before_run`** — injects remembered facts into the prompt\n"
            "- **`after_run`** — extracts new facts from user messages\n\n"
            "An `InMemoryHistoryProvider` persists full chat history server-side."
        )

        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(label="Conversation", height=400)

                with gr.Row():
                    user_input = gr.Textbox(
                        label="Your Message",
                        placeholder="Tell the agent about yourself...",
                        lines=1,
                        scale=4,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                clear_btn = gr.Button("New Session (clear memory)", variant="secondary")

                gr.Examples(
                    examples=STARTER_PROMPTS,
                    inputs=user_input,
                    label="Try this flow",
                )

            with gr.Column(scale=1):
                gr.Markdown("### Agent Memory")
                gr.Markdown("*Facts extracted by the context provider:*")
                memory_display = gr.Textbox(
                    label="Stored Facts",
                    value="No memories stored yet.",
                    interactive=False,
                    lines=10,
                )

        send_btn.click(
            fn=chat,
            inputs=[user_input, chatbot],
            outputs=[chatbot, user_input, memory_display],
        )
        user_input.submit(
            fn=chat,
            inputs=[user_input, chatbot],
            outputs=[chatbot, user_input, memory_display],
        )
        clear_btn.click(
            fn=reset_session,
            outputs=[chatbot, user_input, memory_display],
        )

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
