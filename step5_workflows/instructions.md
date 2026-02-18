# Step 5: Workflows — Executors, Edges & Events

## What is a Workflow?

A workflow is a **directed graph** of executors connected by edges. Each executor performs one unit of work, edges define the flow, and conditional edges enable branching logic.

## Key concepts

### Executors

An executor is a node in the graph. Two ways to define one:

**1. Class-based** (for multi-step logic):
```python
class BuildDockerImage(Executor):
    def __init__(self):
        super().__init__(id="build_docker_image")

    @handler(input=PipelineState, output=PipelineState)
    async def handle(self, state, ctx) -> None:
        state.build_tag = f"app:{state.commit_sha[:7]}"
        await ctx.send_message(state)  # forward to next node
```

**2. Function-based** (for simple terminal steps):
```python
@executor(id="deployment_success_alert")
async def deployment_success_alert(
    state: PipelineState, ctx: WorkflowContext[Never, PipelineState]
) -> None:
    await ctx.yield_output(state)  # terminal — yields workflow output
```

### Message passing

- **`ctx.send_message(data)`** — forwards data to downstream executor(s)
- **`ctx.yield_output(data)`** — marks this as a terminal node and yields the workflow result

### Edges

Edges connect executors. Three patterns:

| Method | Use case |
|--------|----------|
| `add_edge(A, B)` | Simple A → B connection |
| `add_chain([A, B, C])` | Sequential chain A → B → C |
| `add_switch_case_edge_group(source, cases)` | Conditional branching |

### Conditional branching

```python
.add_switch_case_edge_group(
    source=run_tests,
    cases=[
        Case(condition=lambda s: s.tests_passed, target=build),
        Default(target=notify),  # fallback if no case matches
    ],
)
```

## CI/CD Pipeline demo

This step simulates a CI/CD pipeline:

```
Run Unit Tests
    ├── tests_passed → Build Docker Image → Deploy to Staging → Promote to Production → Success Alert
    └── tests_failed → Notify Dev Team → STOP
```

- **`main` branch** — tests pass, full deployment to production
- **`bugfix` branch** — tests fail, dev team notified, pipeline stops

## Setup

Uses the `agent-framework` package (already installed in Step 4):

```bash
pip install agent-framework --pre
```

## Reference

- [Agent Framework Workflow samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/03-workflows)
- [Executor & Edge starter sample](https://github.com/microsoft/agent-framework/blob/main/python/samples/03-workflows/_start-here/step1_executors_and_edges.py)
