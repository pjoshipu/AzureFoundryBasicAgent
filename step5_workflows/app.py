# Step 5: Workflows — CI/CD Pipeline with Executors, Edges & Events
import asyncio
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
)
from agent_framework._workflows import Case, Default, WorkflowViz
from typing_extensions import Never


# ---------------------------------------------------------------------------
# Data model passed between executors
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
        self.step_log.append({
            "step": step, "status": status, "detail": detail, "ts": time.strftime("%H:%M:%S"),
        })


# ---------------------------------------------------------------------------
# Executors (each simulates a CI/CD stage)
# ---------------------------------------------------------------------------
class RunUnitTests(Executor):
    """Run unit tests — passes for 'main', fails for 'bugfix'."""

    def __init__(self):
        super().__init__(id="run_unit_tests")

    @handler(input=PipelineState, output=PipelineState)
    async def handle(self, state, ctx) -> None:
        await asyncio.sleep(0.3)
        state.tests_passed = state.branch != "bugfix"
        status = "passed" if state.tests_passed else "failed"
        state.events.append(f"Unit tests {status} for {state.commit_sha}")
        state.log("Run Unit Tests", status, f"Branch: {state.branch}")
        await ctx.send_message(state)


class NotifyDevTeam(Executor):
    """Notify dev team about failure — terminal node."""

    def __init__(self):
        super().__init__(id="notify_dev_team")

    @handler(input=PipelineState, workflow_output=PipelineState)
    async def handle(self, state, ctx) -> None:
        await asyncio.sleep(0.2)
        state.events.append(f"ALERT: Dev team notified — tests failed on {state.branch}/{state.commit_sha}")
        state.log("Notify Dev Team", "sent", "Pipeline stopped due to test failure")
        await ctx.yield_output(state)


class BuildDockerImage(Executor):
    """Build Docker image from tested commit."""

    def __init__(self):
        super().__init__(id="build_docker_image")

    @handler(input=PipelineState, output=PipelineState)
    async def handle(self, state, ctx) -> None:
        await asyncio.sleep(0.4)
        state.build_tag = f"app:{state.commit_sha[:7]}"
        state.events.append(f"Docker image built: {state.build_tag}")
        state.log("Build Docker Image", "success", f"Tag: {state.build_tag}")
        await ctx.send_message(state)


class DeployToStaging(Executor):
    """Deploy to staging environment."""

    def __init__(self):
        super().__init__(id="deploy_to_staging")

    @handler(input=PipelineState, output=PipelineState)
    async def handle(self, state, ctx) -> None:
        await asyncio.sleep(0.3)
        state.deployed_to = "staging"
        state.events.append(f"Deployed {state.build_tag} to staging — smoke test passed")
        state.log("Deploy to Staging", "deployed", f"Image: {state.build_tag}")
        await ctx.send_message(state)


class PromoteToProduction(Executor):
    """Promote staging deployment to production."""

    def __init__(self):
        super().__init__(id="promote_to_production")

    @handler(input=PipelineState, output=PipelineState)
    async def handle(self, state, ctx) -> None:
        await asyncio.sleep(0.3)
        state.deployed_to = "production"
        state.events.append(f"Promoted {state.build_tag} to production")
        state.log("Promote to Production", "live", f"Image: {state.build_tag}")
        await ctx.send_message(state)


@executor(id="deployment_success_alert")
async def deployment_success_alert(
    state: PipelineState, ctx: WorkflowContext[Never, PipelineState]
) -> None:
    """Send deployment success event — terminal node (yields workflow output)."""
    await asyncio.sleep(0.1)
    state.events.append(f"EVENT: Deployment success — {state.build_tag} is live in production!")
    state.log("Deployment Success Alert", "sent", "All stakeholders notified")
    await ctx.yield_output(state)


# ---------------------------------------------------------------------------
# Build the workflow graph
# ---------------------------------------------------------------------------
def create_workflow():
    run_tests = RunUnitTests()
    notify = NotifyDevTeam()
    build = BuildDockerImage()
    staging = DeployToStaging()
    promote = PromoteToProduction()

    return (
        WorkflowBuilder(name="CI/CD Pipeline", start_executor=run_tests)
        # Conditional edge: tests passed → build, tests failed → notify (stop)
        .add_switch_case_edge_group(
            source=run_tests,
            cases=[
                Case(condition=lambda s: s.tests_passed, target=build),
                Default(target=notify),
            ],
        )
        # Happy path chain: build → staging → promote → success alert
        .add_chain([build, staging, promote, deployment_success_alert])
        .build()
    )


# Generate Mermaid diagram
try:
    mermaid_diagram = WorkflowViz(create_workflow()).to_mermaid()
except Exception:
    mermaid_diagram = "Mermaid diagram generation not available."


# ---------------------------------------------------------------------------
# Run workflow
# ---------------------------------------------------------------------------
def run_pipeline(branch: str):
    try:
        wf = create_workflow()
        state = PipelineState(commit_sha="a1b2c3d", branch=branch)

        # Run in a new event loop to avoid conflict with Gradio's loop
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(wf.run(state))
        finally:
            loop.close()

        outputs = result.get_outputs()
        final_state = outputs[0] if outputs else state

        # Format event log
        event_log = "\n".join(f"  {i+1}. {e}" for i, e in enumerate(final_state.events))

        # Format step table
        step_table = ""
        for s in final_state.step_log:
            step_table += f"| {s['ts']} | {s['step']:<28} | {s['status']:<10} | {s['detail']} |\n"

        outcome = (
            "Deployed to production"
            if final_state.deployed_to == "production"
            else "Pipeline stopped — tests failed"
        )

        summary = (
            f"**Branch:** `{final_state.branch}` | **Commit:** `{final_state.commit_sha}`\n\n"
            f"**Final state:** `{final_state.deployed_to or 'pipeline stopped'}`\n\n"
            f"---\n### Event Log\n{event_log}\n\n"
            f"---\n### Step Details\n"
            f"| Time | Step | Status | Detail |\n"
            f"|------|------|--------|--------|\n{step_table}"
        )

        return outcome, summary

    except Exception as e:
        error = f"Error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        return "Error", error


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
guide_path = Path(__file__).parent / "instructions.md"
guide_content = guide_path.read_text(encoding="utf-8") if guide_path.exists() else "instructions.md not found."

PIPELINE_DIAGRAM = """
```
                    ┌─────────────────────┐
                    │   Run Unit Tests    │
                    └─────────┬───────────┘
                              │
               ┌──────────────┴──────────────┐
               │                             │
        tests_passed                   tests_failed
               │                             │
               ▼                             ▼
    ┌──────────────────┐         ┌───────────────────┐
    │ Build Docker     │         │ Notify Dev Team   │
    │ Image            │         │ → STOP            │
    └────────┬─────────┘         └───────────────────┘
             │
             ▼
    ┌──────────────────┐
    │ Deploy to        │
    │ Staging          │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Promote to       │
    │ Production       │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ EVENT:           │
    │ Deployment       │
    │ Success Alert    │
    └──────────────────┘
```
"""

with gr.Blocks(title="Step 5: Workflows") as app:
    gr.Markdown("# Step 5: Workflows — CI/CD Pipeline")
    gr.Markdown(
        "A workflow built with **Executors**, **Edges**, and **Events** using the "
        "Microsoft Agent Framework. Each executor simulates a CI/CD stage."
    )

    with gr.Tab("Run Pipeline"):
        gr.Markdown("### Pipeline Flow")
        gr.Markdown(PIPELINE_DIAGRAM)

        gr.Markdown("---")
        gr.Markdown("### Run it")
        gr.Markdown(
            "Choose a branch to simulate:\n"
            '- **`main`** — tests pass → full deployment to production\n'
            '- **`bugfix`** — tests fail → dev team notified, pipeline stops'
        )

        with gr.Row():
            branch_input = gr.Radio(
                choices=["main", "bugfix"],
                value="main",
                label="Branch",
            )
            run_btn = gr.Button("Run Pipeline", variant="primary")

        outcome_output = gr.Textbox(label="Outcome", interactive=False)
        detail_output = gr.Markdown(label="Pipeline Details")

        run_btn.click(
            fn=run_pipeline,
            inputs=branch_input,
            outputs=[outcome_output, detail_output],
        )

    with gr.Tab("Workflow Graph"):
        gr.Markdown("### Mermaid Diagram (auto-generated)")
        gr.Markdown(
            "Generated by `WorkflowViz(workflow).to_mermaid()` — "
            "paste into any Mermaid renderer to visualize."
        )
        gr.Code(value=mermaid_diagram, language=None, label="Mermaid Source")

    with gr.Tab("Setup Guide"):
        gr.Markdown(guide_content)

app.launch(footer_links=[])
