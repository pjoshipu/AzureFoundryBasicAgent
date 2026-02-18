# Step 3: Multi-Turn Conversations

## What is multi-turn?

In Step 1, every message was independent — the agent had no memory of prior exchanges. Multi-turn means the agent **remembers the full conversation** so it can reference earlier messages.

## How it works: `previous_response_id`

The OpenAI Responses API supports conversation chaining natively:

1. **First message** — call `responses.create(...)` normally, get back a response with an `id`
2. **Follow-up messages** — pass `previous_response_id=<last response id>` so the API links the new request to the prior conversation
3. **Server-side history** — the API stores the full conversation; you don't need to resend all messages each time

```python
# First turn
response = client.responses.create(
    model="gpt-4o-mini",
    input=[{"role": "user", "content": "My name is Raj."}],
)

# Second turn — agent remembers "Alex"
response = client.responses.create(
    model="gpt-4o-mini",
    input=[{"role": "user", "content": "What's my name?"}],
    previous_response_id=response.id,
)
```

## Demo flow

1. Tell the agent some facts: *"Hi! My name is Raj, I'm a cloud architect from Atlanta, Georgia."*
2. Add more details: *"I have two cats named Pixel and Byte, and I'm learning to play guitar."*
3. Ask: *"What do you remember about me?"*
4. The agent recalls everything from the session.
5. Click **New Conversation** to reset — the agent forgets everything.

## Key difference from Step 1

| | Step 1 | Step 3 |
|---|---|---|
| Context | Single message | Full conversation history |
| API param | — | `previous_response_id` |
| Memory | None | Server-side via response chain |

## No additional setup required

Uses the same model deployment and credentials from Step 1.
