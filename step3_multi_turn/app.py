# Step 3: Multi-Turn Conversations using previous_response_id
import os
import sys
import traceback
from pathlib import Path

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from shared import get_openai_client

openai_client = get_openai_client()

MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")

INSTRUCTIONS = (
    "You are a friendly, attentive assistant with a great memory. "
    "Pay close attention to any personal details the user shares (name, hobbies, "
    "job, favorites, etc.). When asked what you remember, always start with: "
    "'According to my memory from our conversation...' and list everything "
    "the user has told you so far."
)

STARTER_PROMPTS = [
    ["Hi! My name is Raj, I'm a cloud architect from Atlanta, Georgia and I love barbecue."],
    ["I have two cats named Pixel and Byte, and I'm learning to play guitar."],
    ["What do you remember about me?"],
]


# ---------------------------------------------------------------------------
# Multi-turn agent session — chains calls via previous_response_id
# ---------------------------------------------------------------------------
def chat(user_message, history, session_id):
    """Send a message and maintain conversation context via previous_response_id."""
    try:
        kwargs = {
            "model": MODEL_DEPLOYMENT_NAME,
            "instructions": INSTRUCTIONS,
            "input": [{"role": "user", "content": user_message}],
        }
        # Chain to previous response if we have a session
        if session_id:
            kwargs["previous_response_id"] = session_id

        response = openai_client.responses.create(**kwargs)

        # Store the response id as our session handle
        new_session_id = response.id
        assistant_reply = response.output_text

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_reply})

        return history, "", new_session_id

    except Exception as e:
        error = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": error})
        return history, "", session_id


def reset_session():
    """Clear chat history and start a fresh session."""
    return [], "", None


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

with gr.Blocks(title="Step 3: Multi-Turn Conversation", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Step 3: Multi-Turn Conversation")
    gr.Markdown(
        "This agent **remembers the entire conversation** using `previous_response_id` to chain "
        "each response to the last. Share some facts about yourself, then ask what it remembers!"
    )

    with gr.Tab("Chat"):
        gr.Markdown("### How it works")
        gr.Markdown(
            "Each API call passes `previous_response_id` pointing to the last response. "
            "The model sees the full conversation history server-side — no need to resend all messages."
        )

        # Hidden state for the session id (previous_response_id)
        session_id = gr.State(value=None)

        chatbot = gr.Chatbot(label="Conversation", height=400)

        with gr.Row():
            user_input = gr.Textbox(
                label="Your Message",
                placeholder="Tell the agent something about yourself...",
                lines=1,
                scale=4,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1)

        with gr.Row():
            clear_btn = gr.Button("New Conversation", variant="secondary")

        gr.Markdown("### Try this flow")
        gr.Examples(
            examples=STARTER_PROMPTS,
            inputs=user_input,
            label="Click a prompt to fill it in, then press Send",
        )

        # Wire events
        send_btn.click(
            fn=chat,
            inputs=[user_input, chatbot, session_id],
            outputs=[chatbot, user_input, session_id],
        )
        user_input.submit(
            fn=chat,
            inputs=[user_input, chatbot, session_id],
            outputs=[chatbot, user_input, session_id],
        )
        clear_btn.click(
            fn=reset_session,
            outputs=[chatbot, user_input, session_id],
        )

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
