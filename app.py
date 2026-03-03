# Azure Agentic SDLC — Combined Gradio app (Vercel entry point)
# All 6 steps in one interface with purple theme
import asyncio
import json
import os
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import gradio as gr
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
PROJECT_ENDPOINT = os.getenv("AZURE_ENDPOINT")

# ---------------------------------------------------------------------------
# Lazy Azure client initialization
# ---------------------------------------------------------------------------
_project_client = None
_openai_client = None


def _get_clients():
    global _project_client, _openai_client
    if _project_client is None:
        from azure.ai.projects import AIProjectClient
        from azure.identity import ClientSecretCredential

        cred = ClientSecretCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),
        )
        _project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=cred)
        _openai_client = _project_client.get_openai_client()
    return _project_client, _openai_client


def _get_azure_responses_client():
    from agent_framework.azure import AzureOpenAIResponsesClient
    from azure.identity import ClientSecretCredential

    cred = ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
    )
    return AzureOpenAIResponsesClient(
        project_endpoint=PROJECT_ENDPOINT,
        deployment_name=MODEL_DEPLOYMENT_NAME,
        credential=cred,
    )


# ---------------------------------------------------------------------------
# Step 1: Basic Agent
# ---------------------------------------------------------------------------
STEP1_CONSTRAINT = 'Keep your response "one-line" only.'


def step1_send(user_prompt):
    try:
        from azure.ai.projects.models import PromptAgentDefinition

        pc, oc = _get_clients()
        agent = pc.agents.create_version(
            agent_name="AzureFoundryAgent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=f"You are a helpful agent.\n\n{STEP1_CONSTRAINT}",
            ),
        )
        response = oc.responses.create(
            input=[{"role": "user", "content": user_prompt}],
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )
        return response.output_text
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}\n\nEnsure Azure env vars are set in Vercel."


# ---------------------------------------------------------------------------
# Step 3: Multi-Turn Conversation
# ---------------------------------------------------------------------------
STEP3_INSTRUCTIONS = (
    "You are a friendly, attentive assistant with a great memory. "
    "Pay close attention to any personal details the user shares. "
    "When asked what you remember, start with: 'According to my memory from our conversation...'"
)


def step3_chat(user_message, history, session_id):
    try:
        _, oc = _get_clients()
        kwargs = {
            "model": MODEL_DEPLOYMENT_NAME,
            "instructions": STEP3_INSTRUCTIONS,
            "input": [{"role": "user", "content": user_message}],
        }
        if session_id:
            kwargs["previous_response_id"] = session_id
        response = oc.responses.create(**kwargs)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response.output_text})
        return history, "", response.id
    except Exception as e:
        err = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": err})
        return history, "", session_id


def step3_reset():
    return [], "", None


# ---------------------------------------------------------------------------
# Step 4: Memory & Persistence
# ---------------------------------------------------------------------------
_step4_facts: list[str] = []
_step4_session_id: str | None = None


def step4_extract_facts(text: str):
    lower = text.lower()
    if "my name is" in lower:
        name = lower.split("my name is")[-1].strip().split()[0].capitalize()
        fact = f"Name: {name}"
        if fact not in _step4_facts:
            _step4_facts.append(fact)
    if "from " in lower and ("live" in lower or "i'm from" in lower or "i am from" in lower):
        location = text.split("from")[-1].strip().rstrip(".,!").split(" and ")[0]
        fact = f"Location: {location}"
        if fact not in _step4_facts:
            _step4_facts.append(fact)
    for kw in ["i'm a ", "i am a ", "i work as ", "my job is "]:
        if kw in lower:
            prof = text.lower().split(kw)[-1].strip().split(".")[0].split(",")[0].split(" and ")[0]
            fact = f"Profession: {prof.title()}"
            if fact not in _step4_facts:
                _step4_facts.append(fact)
    for kw in ["i love ", "i like ", "i enjoy ", "my hobby is "]:
        if kw in lower:
            interest = text.lower().split(kw)[-1].strip().rstrip(".,!").split(" and ")[0]
            fact = f"Interest: {interest.title()}"
            if fact not in _step4_facts:
                _step4_facts.append(fact)


def step4_chat(user_message, history):
    global _step4_session_id
    try:
        _, oc = _get_clients()
        mem_block = ""
        if _step4_facts:
            mem_block = "Known facts about the user:\n" + "\n".join(f"- {f}" for f in _step4_facts)
        instructions = (
            "You are a friendly, attentive assistant. Be warm and conversational.\n\n"
            + (mem_block if mem_block else "You don't know anything about the user yet. Be friendly.")
        )
        kwargs = {
            "model": MODEL_DEPLOYMENT_NAME,
            "instructions": instructions,
            "input": [{"role": "user", "content": user_message}],
        }
        if _step4_session_id:
            kwargs["previous_response_id"] = _step4_session_id
        response = oc.responses.create(**kwargs)
        _step4_session_id = response.id
        step4_extract_facts(user_message)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response.output_text})
        mem_display = "\n".join(f"- {f}" for f in _step4_facts) if _step4_facts else "No memories stored yet."
        return history, "", mem_display
    except Exception as e:
        err = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": err})
        return history, "", "\n".join(f"- {f}" for f in _step4_facts) if _step4_facts else "No memories stored yet."


def step4_reset():
    global _step4_facts, _step4_session_id
    _step4_facts = []
    _step4_session_id = None
    return [], "", "No memories stored yet."


# ---------------------------------------------------------------------------
# Step 5: Workflows — CI/CD Pipeline
# ---------------------------------------------------------------------------
@dataclass
class PipelineState:
    commit_sha: str = "a1b2c3d"
    branch: str = "main"
    tests_passed: bool = False
    build_tag: str = ""
    deployed_to: str = ""
    events: list[str] = field(default_factory=list)
    step_log: list[dict] = field(default_factory=list)

    def log(self, step: str, status: str, detail: str = ""):
        self.step_log.append({"step": step, "status": status, "detail": detail, "ts": time.strftime("%H:%M:%S")})


def step5_run_pipeline(branch: str):
    try:
        from agent_framework import WorkflowBuilder, executor, handler, Executor, WorkflowContext
        from agent_framework._workflows import Case, Default
        from typing_extensions import Never

        class RunUnitTests(Executor):
            def __init__(self):
                super().__init__(id="run_unit_tests")

            @handler(input=PipelineState, output=PipelineState)
            async def handle(self, state, ctx):
                await asyncio.sleep(0.3)
                state.tests_passed = state.branch != "bugfix"
                status = "passed" if state.tests_passed else "failed"
                state.events.append(f"Unit tests {status} for {state.commit_sha}")
                state.log("Run Unit Tests", status, f"Branch: {state.branch}")
                await ctx.send_message(state)

        class NotifyDevTeam(Executor):
            def __init__(self):
                super().__init__(id="notify_dev_team")

            @handler(input=PipelineState, workflow_output=PipelineState)
            async def handle(self, state, ctx):
                await asyncio.sleep(0.2)
                state.events.append(f"ALERT: Dev team notified — tests failed on {state.branch}/{state.commit_sha}")
                state.log("Notify Dev Team", "sent", "Pipeline stopped due to test failure")
                await ctx.yield_output(state)

        class BuildDockerImage(Executor):
            def __init__(self):
                super().__init__(id="build_docker_image")

            @handler(input=PipelineState, output=PipelineState)
            async def handle(self, state, ctx):
                await asyncio.sleep(0.4)
                state.build_tag = f"app:{state.commit_sha[:7]}"
                state.events.append(f"Docker image built: {state.build_tag}")
                state.log("Build Docker Image", "success", f"Tag: {state.build_tag}")
                await ctx.send_message(state)

        class DeployToStaging(Executor):
            def __init__(self):
                super().__init__(id="deploy_to_staging")

            @handler(input=PipelineState, output=PipelineState)
            async def handle(self, state, ctx):
                await asyncio.sleep(0.3)
                state.deployed_to = "staging"
                state.events.append(f"Deployed {state.build_tag} to staging")
                state.log("Deploy to Staging", "deployed", f"Image: {state.build_tag}")
                await ctx.send_message(state)

        class PromoteToProduction(Executor):
            def __init__(self):
                super().__init__(id="promote_to_production")

            @handler(input=PipelineState, output=PipelineState)
            async def handle(self, state, ctx):
                await asyncio.sleep(0.3)
                state.deployed_to = "production"
                state.events.append(f"Promoted {state.build_tag} to production")
                state.log("Promote to Production", "live", f"Image: {state.build_tag}")
                await ctx.send_message(state)

        @executor(id="deployment_success_alert")
        async def deployment_success_alert(state: PipelineState, ctx: WorkflowContext[Never, PipelineState]):
            await asyncio.sleep(0.1)
            state.events.append(f"EVENT: Deployment success — {state.build_tag} is live in production!")
            state.log("Deployment Success Alert", "sent", "All stakeholders notified")
            await ctx.yield_output(state)

        run_tests = RunUnitTests()
        notify = NotifyDevTeam()
        build = BuildDockerImage()
        staging = DeployToStaging()
        promote = PromoteToProduction()

        wf = (
            WorkflowBuilder(name="CI/CD Pipeline", start_executor=run_tests)
            .add_switch_case_edge_group(
                source=run_tests,
                cases=[Case(condition=lambda s: s.tests_passed, target=build), Default(target=notify)],
            )
            .add_chain([build, staging, promote, deployment_success_alert])
            .build()
        )

        state = PipelineState(commit_sha="a1b2c3d", branch=branch)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(wf.run(state))
        finally:
            loop.close()

        outputs = result.get_outputs()
        final = outputs[0] if outputs else state
        event_log = "\n".join(f"  {i+1}. {e}" for i, e in enumerate(final.events))
        step_table = "".join(
            f"| {s['ts']} | {s['step']:<28} | {s['status']:<10} | {s['detail']} |\n" for s in final.step_log
        )
        outcome = "Deployed to production" if final.deployed_to == "production" else "Pipeline stopped — tests failed"
        summary = (
            f"**Branch:** `{final.branch}` | **Commit:** `{final.commit_sha}`\n\n"
            f"**Final state:** `{final.deployed_to or 'pipeline stopped'}`\n\n"
            f"---\n### Event Log\n{event_log}\n\n"
            f"---\n### Step Details\n| Time | Step | Status | Detail |\n|------|------|--------|--------|\n{step_table}"
        )
        return outcome, summary
    except Exception as e:
        return "Error", f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Step 6: Hosting Test Client
# ---------------------------------------------------------------------------
def step6_check_health(base_url):
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/health", timeout=5)
        return f"Healthy (HTTP {resp.status_code})" if resp.status_code == 200 else f"HTTP {resp.status_code}: {resp.text}"
    except requests.ConnectionError:
        return "Not reachable — is `func start` running?"
    except Exception as e:
        return f"Error: {e}"


def step6_send(user_prompt, base_url):
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/agents/HostedAgent/run",
            headers={"Content-Type": "text/plain"},
            data=user_prompt,
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.text, f"Status: {resp.status_code} OK"
        elif resp.status_code == 202:
            return f"Accepted (async):\n{json.dumps(resp.json(), indent=2)}", f"Status: 202 Accepted"
        return f"HTTP {resp.status_code}: {resp.text}", f"Status: {resp.status_code}"
    except requests.ConnectionError:
        return "Connection refused. Start with: cd step6_hosting && func start", "Status: Connection Error"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}", "Status: Error"


# ---------------------------------------------------------------------------
# Build the combined Gradio interface
# ---------------------------------------------------------------------------
PURPLE = gr.themes.Soft(primary_hue="purple")

with gr.Blocks(title="Azure Agentic SDLC", theme=PURPLE) as demo:
    gr.Markdown("# Azure Agentic SDLC")
    gr.Markdown(
        "A 6-step journey from a basic Azure Foundry Agent to a production-hosted deployment. "
        "Each tab is a self-contained step — run them in order to build understanding progressively."
    )

    # ── Step 1 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 1: Basic Agent"):
        gr.Markdown("## Step 1: Basic Azure Foundry Agent")
        gr.Markdown("Send a single prompt and receive a one-line response from the agent.")
        s1_constraint = gr.Textbox(label="Response Constraint", value=STEP1_CONSTRAINT, interactive=False)
        s1_prompt = gr.Textbox(label="Your Prompt", placeholder="e.g., Tell me a one line story", lines=2)
        s1_btn = gr.Button("Send", variant="primary")
        s1_response = gr.Textbox(label="Response", interactive=False)
        s1_btn.click(fn=step1_send, inputs=s1_prompt, outputs=s1_response)

    # ── Step 2 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 2: Tools"):
        gr.Markdown("## Step 2: Agent with Tools")
        gr.Markdown(
            "Coming soon — this step will demonstrate **function calling** with tools like "
            "weather lookup, product search, and knowledge base querying.\n\n"
            "The agent below works the same as Step 1 while tool support is being added."
        )
        s2_prompt = gr.Textbox(label="Your Prompt", placeholder="e.g., What is the weather in Atlanta?", lines=2)
        s2_btn = gr.Button("Send", variant="primary")
        s2_response = gr.Textbox(label="Response", interactive=False)
        s2_btn.click(fn=step1_send, inputs=s2_prompt, outputs=s2_response)

    # ── Step 3 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 3: Multi-Turn"):
        gr.Markdown("## Step 3: Multi-Turn Conversation")
        gr.Markdown(
            "The agent chains each call via `previous_response_id` — the model remembers your "
            "entire conversation without you resending old messages."
        )
        s3_session = gr.State(value=None)
        s3_chatbot = gr.Chatbot(label="Conversation", height=400)
        with gr.Row():
            s3_input = gr.Textbox(label="Your Message", placeholder="Tell the agent something about yourself...", lines=1, scale=4)
            s3_send = gr.Button("Send", variant="primary", scale=1)
        s3_clear = gr.Button("New Conversation", variant="secondary")
        gr.Examples(
            examples=[
                ["Hi! My name is Raj, I'm a cloud architect from Atlanta, Georgia and I love barbecue."],
                ["I have two cats named Pixel and Byte, and I'm learning to play guitar."],
                ["What do you remember about me?"],
            ],
            inputs=s3_input,
            label="Click a prompt, then press Send",
        )
        s3_send.click(fn=step3_chat, inputs=[s3_input, s3_chatbot, s3_session], outputs=[s3_chatbot, s3_input, s3_session])
        s3_input.submit(fn=step3_chat, inputs=[s3_input, s3_chatbot, s3_session], outputs=[s3_chatbot, s3_input, s3_session])
        s3_clear.click(fn=step3_reset, outputs=[s3_chatbot, s3_input, s3_session])

    # ── Step 4 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 4: Memory"):
        gr.Markdown("## Step 4: Memory & Persistence")
        gr.Markdown(
            "A Context Provider extracts facts from messages and injects them into subsequent calls. "
            "Watch the **Agent Memory** panel update in real time."
        )
        with gr.Row():
            with gr.Column(scale=3):
                s4_chatbot = gr.Chatbot(label="Conversation", height=400)
                with gr.Row():
                    s4_input = gr.Textbox(label="Your Message", placeholder="Tell the agent about yourself...", lines=1, scale=4)
                    s4_send = gr.Button("Send", variant="primary", scale=1)
                s4_clear = gr.Button("New Session (clear memory)", variant="secondary")
                gr.Examples(
                    examples=[
                        ["Hi! My name is Raj, I'm a cloud architect from Atlanta, Georgia."],
                        ["I love barbecue and I enjoy hiking on weekends."],
                        ["What do you remember about me?"],
                    ],
                    inputs=s4_input,
                    label="Try this flow",
                )
            with gr.Column(scale=1):
                gr.Markdown("### Agent Memory")
                gr.Markdown("*Facts extracted by the context provider:*")
                s4_memory = gr.Textbox(label="Stored Facts", value="No memories stored yet.", interactive=False, lines=10)
        s4_send.click(fn=step4_chat, inputs=[s4_input, s4_chatbot], outputs=[s4_chatbot, s4_input, s4_memory])
        s4_input.submit(fn=step4_chat, inputs=[s4_input, s4_chatbot], outputs=[s4_chatbot, s4_input, s4_memory])
        s4_clear.click(fn=step4_reset, outputs=[s4_chatbot, s4_input, s4_memory])

    # ── Step 5 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 5: Workflows"):
        gr.Markdown("## Step 5: Workflows — CI/CD Pipeline")
        gr.Markdown(
            "A workflow built with **Executors**, **Edges**, and **Events**. "
            "Choose a branch to simulate the pipeline:"
        )
        gr.Markdown(
            "- **`main`** — tests pass → full deployment to production\n"
            "- **`bugfix`** — tests fail → dev team notified, pipeline stops"
        )
        with gr.Row():
            s5_branch = gr.Radio(choices=["main", "bugfix"], value="main", label="Branch")
            s5_run = gr.Button("Run Pipeline", variant="primary")
        s5_outcome = gr.Textbox(label="Outcome", interactive=False)
        s5_detail = gr.Markdown(label="Pipeline Details")
        s5_run.click(fn=step5_run_pipeline, inputs=s5_branch, outputs=[s5_outcome, s5_detail])

    # ── Step 6 ──────────────────────────────────────────────────────────────
    with gr.Tab("Step 6: Hosting"):
        gr.Markdown("## Step 6: Host Your Agent")
        gr.Markdown(
            "Test your agent hosted via **Azure Functions**. "
            "Start the host locally with `cd step6_hosting && func start`."
        )
        s6_base_url = gr.Textbox(label="Functions Base URL", value="http://localhost:7071", interactive=True)
        with gr.Row():
            s6_health_btn = gr.Button("Check Health", variant="secondary")
            s6_health = gr.Textbox(label="Health Status", interactive=False)
        s6_health_btn.click(fn=step6_check_health, inputs=s6_base_url, outputs=s6_health)
        gr.Markdown("---")
        s6_prompt = gr.Textbox(label="Your Prompt", placeholder="Type a message to send to the hosted agent...", lines=2)
        s6_send = gr.Button("Send", variant="primary")
        s6_response = gr.Textbox(label="Agent Response", interactive=False, lines=4)
        s6_status = gr.Textbox(label="HTTP Status", interactive=False)
        s6_send.click(fn=step6_send, inputs=[s6_prompt, s6_base_url], outputs=[s6_response, s6_status])

# Expose the underlying FastAPI app for Vercel's Python runtime
app = demo.app

if __name__ == "__main__":
    demo.launch()
