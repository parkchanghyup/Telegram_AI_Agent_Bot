# Telegram MCP Bot

An extensible Telegram bot that uses LLMs (OpenAI or Ollama) and connects to MCP (Multi‑Capability) servers to perform tool‑augmented tasks.

## Quick start

### 1) Configure environment variables

Create a `.env` file in the project root and set the variables for your environment:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"ㅋ

# LLM provider: "openai" or "ollama"
LLM_PROVIDER="openai"

# --- OpenAI settings (when LLM_PROVIDER=openai) ---
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
# Optional model overrides
# QA_MODEL_NAME="gpt-5-nano"
# NAVER_MODEL_NAME="gpt-5-mini"
# TRIAGE_MODEL_NAME="gpt-5-mini"

# --- Ollama settings (when LLM_PROVIDER=ollama) ---
OLLAMA_BASE_URL="http://localhost:11434/v1"
# If not set, defaults to "conandoyle247/jan-nano-4b-gguf" as configured in src/config.py
# OLLAMA_MODEL="llama3.1"

# --- Naver Search MCP server ---
NAVER_CLIENT_ID="YOUR_NAVER_CLIENT_ID"
NAVER_CLIENT_SECRET="YOUR_NAVER_CLIENT_SECRET"
```

Notes:
- The bot loads configuration from `.env` at startup.
- When `LLM_PROVIDER=openai`, `OPENAI_API_KEY` is required.
- When `LLM_PROVIDER=ollama`, the code uses an OpenAI‑compatible client pointed at `OLLAMA_BASE_URL` and the `OLLAMA_MODEL` name.

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure MCP servers

`mcp_config.json` defines the MCP servers the bot will start and connect to. By default, a Naver News search server is included.

Key points:
- `command` is the Python interpreter to run the server (e.g., `python` or your virtualenv path).
- Provide script paths in `args`. Paths starting with `src/` are automatically resolved relative to the project root.

Example `mcp_config.json`:

```json
{
  "mcpServers": {
    "naver-search": {
      "command": "python",
      "args": ["src/naver_mcp_server.py"]
    }
  }
}
```

You can add more servers by inserting additional entries under `mcpServers`.

### 4) Run the bot

```bash
python main.py
```

Once running, open Telegram and send a message to your bot. The active agent will respond using the configured LLM provider.

## How it works

- A triage agent routes requests to specialized agents:
  - QnA Agent (general questions)
  - Naver Search Agent (news search via the MCP server)
- The Naver MCP server calls Naver’s news API, fetches full article text, and returns structured results to the agent.

## Extending the bot (add MCP tools and agents)

### 1) Implement a new MCP server

Place your server script under `src/`, for example `src/my_custom_server.py`. Expose tools using the FastMCP interface so agents can call them.

### 2) Register the server in `mcp_config.json`

```json
{
  "mcpServers": {
    "naver-search": {
      "command": "python",
      "args": ["src/naver_mcp_server.py"]
    },
    "my-custom-server": {
      "command": "python",
      "args": ["src/my_custom_server.py"]
    }
  }
}
```

### 3) Create a new agent in `src/agent_setup.py`

In `setup_agent_and_servers`, load your prompt and include the agent. Example:

```python
CUSTOM_AGENT_INSTRUCTIONS = load_prompt("custom_agent.txt", prompt_base_dir)
custom_server = mcp_server_map.get("my-custom-server")

custom_agent = Agent(
    name="Custom Function Agent",
    instructions=CUSTOM_AGENT_INSTRUCTIONS,
    model=llm_factory.create_llm_model("gpt-5-nano"),
    mcp_servers=[custom_server] if custom_server else []
)

triage_agent = Agent(
    name="Triage Agent",
    instructions=TRIAGE_AGENT_INSTRUCTIONS,
    handoffs=[naver_agent, qa_agent, custom_agent],
    model=llm_factory.get_triage_model()
)
```

Add the corresponding prompt file under `src/prompt/custom_agent.txt`.

## Logging

- Application logs are written to stdout and to `logs/bot.log`.
- The Naver MCP server writes to `logs/naver_mcp_server.log`.

## Troubleshooting

- Missing `TELEGRAM_BOT_TOKEN`: set it in `.env`.
- `LLM_PROVIDER=openai` requires `OPENAI_API_KEY`.
- `LLM_PROVIDER=ollama` requires a running Ollama instance with OpenAI‑compatible API at `OLLAMA_BASE_URL` and a valid `OLLAMA_MODEL`.
- Naver search requires `NAVER_CLIENT_ID` and `NAVER_CLIENT_SECRET`.
