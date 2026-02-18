# Step 2: Add Tools to Your Agent

## What are Tools?

Tools (also called "function calling") let your agent **call your code** to fetch real data before answering. Instead of guessing, the agent can:

- **Call an API** — e.g., get live weather, stock prices, or search results
- **Query a database** — e.g., look up products, users, or orders
- **Search documents** — e.g., find relevant knowledge base articles or FAQs

## How it works

1. You define **tool schemas** (JSON) describing each function's name, description, and parameters
2. You pass these schemas to the agent via the `tools` parameter
3. The agent decides **when and which** tool to call based on the user's question
4. Your code **executes the function** and returns the result
5. The agent uses the result to compose a natural language answer
6. This loop repeats if the agent needs to call multiple tools

## Tools in this demo

| Tool | Simulates | Example prompt |
|------|-----------|---------------|
| `get_weather` | External API call | "What's the weather in Seattle?" |
| `query_products` | Database query | "Show me electronics under $50" |
| `search_knowledge_base` | Knowledge base / search API | "What is your return policy?" |

## Key code changes from Step 1

- **Tool definitions** — `TOOL_DEFINITIONS` list with JSON schemas for each function
- **Tool implementations** — Python functions that return JSON strings (simulated data)
- **Tool-calling loop** — After each `responses.create`, check for `function_call` outputs, execute them, and feed results back via `function_call_output`
- **`previous_response_id`** — Links follow-up calls to the conversation context

## No additional setup required

This step uses the same Azure Foundry agent and credentials from Step 1. The tools are defined entirely in your code — no extra Azure portal configuration needed.
