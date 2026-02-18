# Step 4: Memory & Persistence

## What changes from Step 3?

Step 3 used `previous_response_id` for multi-turn — the API kept chat history, but the agent had no structured memory. In Step 4, we use the **Microsoft Agent Framework** with **Context Providers** that actively extract, store, and inject user facts into every call.

## Key concepts

### Context Providers (`BaseContextProvider`)

A context provider hooks into the agent lifecycle:

- **`before_run`** — runs before the model call. Injects remembered facts into the prompt instructions.
- **`after_run`** — runs after the model call. Extracts new facts from the user's message.

```python
class UserPreferencesProvider(BaseContextProvider):
    async def before_run(self, *, agent, session, context, state):
        # Inject known facts into context.instructions
        context.instructions.append(f"User's name is {self.name}")

    async def after_run(self, *, agent, session, context, state):
        # Extract facts from context.input_messages
        for msg in context.input_messages:
            if "my name is" in msg.text.lower():
                self.name = ...  # parse it out
```

### History Provider (`InMemoryHistoryProvider`)

Persists full chat history across turns so the agent sees prior messages:

```python
from agent_framework._sessions import InMemoryHistoryProvider

history = InMemoryHistoryProvider("memory", load_messages=True)
```

### Agent Framework client (`AzureOpenAIResponsesClient`)

Replaces the raw `openai_client.responses.create()` pattern with a higher-level API:

```python
from agent_framework.azure import AzureOpenAIResponsesClient

client = AzureOpenAIResponsesClient(
    project_endpoint=os.environ["AZURE_ENDPOINT"],
    deployment_name=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)

agent = client.as_agent(
    name="MemoryAgent",
    instructions="You are a friendly assistant.",
    context_providers=[memory_provider, history_provider],
)

session = agent.create_session()
result = await agent.run("Hello!", session=session)
```

## What the demo extracts

The `UserPreferencesProvider` parses user messages for:

| Pattern | Extracted as |
|---------|-------------|
| "My name is Raj" | `Name: Raj` |
| "I'm from Atlanta" | `Location: Atlanta` |
| "I'm a cloud architect" | `Profession: Cloud Architect` |
| "I love barbecue" | `Interest: Barbecue` |

The **Memory panel** on the right shows stored facts in real-time.

## Setup

Install the Agent Framework (preview):

```bash
pip install agent-framework --pre
```

Uses the same Azure credentials and endpoint from earlier steps.

## Reference

- [Microsoft Agent Framework - Memory docs](https://learn.microsoft.com/en-us/agent-framework/get-started/memory?pivots=programming-language-python)
- [Full sample on GitHub](https://github.com/microsoft/agent-framework/blob/main/python/samples/01-get-started/04_memory.py)
