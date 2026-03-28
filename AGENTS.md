# AGENTS.md — Guide for Coding Agents

> Read this file before editing anything in the repo. It provides enough context to work without having to re-read the full codebase.

---

## Overview

**Research Agent** is an orchestrator agent for researching T-shirt trends on Etsy and social media. It coordinates multiple specialized sub-agents (Google Trends, Etsy, TikTok, Twitter, Reddit, Tavily) and synthesizes their results into a report.

**Framework**: LangGraph + `deepagents` library  
**LLM**: Azure OpenAI or Google Gemini (configured via `.env`)

---

## Directory Structure

```
Research-Agents/
├── agent.py                    # Entry point — creates research_agent for LangGraph
├── app.py                      # Chainlit UI app (thin entry point)
├── run_cli.py                  # Manual CLI runner
├── langgraph.json              # LangGraph deploy config
├── pyproject.toml
│
├── chainlit_app/               # Modular Chainlit UI layer
│   ├── __init__.py
│   ├── auth.py                 # @cl.password_auth_callback + optional auto-login
│   ├── charts.py               # attach_charts() — attaches new PNGs after each run
│   ├── data_layer.py           # SQLiteDataLayer — persists threads/steps/elements
│   └── stream_handler.py       # handle_message() — streams agent output to UI
│
├── research_agent/             # Main package
│   ├── __init__.py             # Re-exports from tools.research
│   ├── config.py               # AppConfig — all env vars in one place
│   ├── prompts.py              # All system prompts (orchestrator + sub-agents)
│   ├── sub_agents.py           # Sub-agent declarations + build_default_registry()
│   │
│   ├── base/
│   │   ├── base.py             # BaseToolkit, BaseSubAgentDef, SubAgentRegistry
│   │   └── __init__.py
│   │
│   └── tools/                  # All tool implementations, grouped by platform
│       ├── __init__.py         # Re-exports all toolkits
│       ├── research.py         # TavilyToolkit + skill_* tools + think tool
│       ├── google.py           # GoogleAISearchToolkit, GoogleTrendsToolkit
│       ├── reddit.py           # RedditToolkit
│       ├── twitter.py          # TwitterToolkit (scraping, no API key needed)
│       ├── tiktok.py           # TikTokTool (requires TIKTOK_MS_TOKEN)
│       └── etsy/
│           ├── __init__.py
│           ├── tools.py        # EtsyToolkit (search_etsy_trends, get_etsy_top_listings)
│           └── analyzer.py     # EtsyTrendAnalyzer — fetch + analysis + chart generation
│
├── docs/                       # Technical documentation
│   ├── architecture.md
│   ├── adding-tools.md
│   └── adding-agents.md
│
├── output/
│   └── etsy_data/              # Etsy API JSON cache (avoids redundant API calls)
├── public/charts/              # Generated chart PNG files
└── skills/                     # LangGraph skill definitions
```

---

## Data Flow

```
User request
    │
    ▼
agent.py (research_agent)           ← orchestrator, has skill_* tools + think
    │  reads prompts.py:RESEARCH_WORKFLOW_TEMPLATE
    │  coordinates sub-agents via deepagents
    │
    ├── google-ai-search-agent      ← GoogleAISearchToolkit
    ├── google-trends-agent         ← GoogleTrendsToolkit  
    ├── tavily-search-agent         ← TavilyToolkit + think
    ├── etsy-search-agent           ← EtsyToolkit → EtsyTrendAnalyzer
    ├── twitter-search-agent        ← TwitterToolkit
    ├── reddit-search-agent         ← RedditToolkit
    └── tiktok-search-agent         ← tiktok_tools (disabled by default)
```

---

## Key Files to Know

| File | When to read |
|------|-------------|
| `research_agent/config.py` | Adding a new env var or config |
| `research_agent/sub_agents.py` | Adding or modifying a sub-agent |
| `research_agent/prompts.py` | Changing agent behavior (prompts) |
| `research_agent/tools/etsy/analyzer.py` | Etsy analysis logic + chart generation |
| `research_agent/base/base.py` | Understanding BaseToolkit / BaseSubAgentDef pattern |
| `chainlit_app/stream_handler.py` | Streaming UI output, tool step rendering |
| `chainlit_app/data_layer.py` | Thread/step persistence (SQLite) |
| `chainlit_app/auth.py` | Authentication, auto-login flag |
| `app.py` | Session lifecycle hooks (`on_chat_start`, `on_chat_resume`) |

---

## How to Add New Features

### 1. Add a new Platform/API (e.g. Pinterest)

```
# Step 1: Create the tool file
research_agent/tools/pinterest.py

# Step 2: Implement BaseToolkit
class PinterestToolkit(BaseToolkit):
    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.pinterest  # add PinterestConfig to config.py
        self._api_key = cfg.api_key
        self._tools = None

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        # define @tool functions here...
        self._tools = [search_pinterest]
        return self._tools

# Step 3: Add config to config.py
@dataclass
class PinterestConfig(BaseConfig):
    api_key: str = field(default_factory=lambda: os.getenv("PINTEREST_API_KEY", ""))

# Step 4: Add to AppConfig
pinterest: PinterestConfig = field(default_factory=PinterestConfig)

# Step 5: Export in tools/__init__.py

# Step 6: Create the sub-agent in sub_agents.py (see below)
```

### 2. Add a new Sub-agent

```python
# In research_agent/sub_agents.py:

class PinterestSearchSubAgent(BaseSubAgentDef):
    name = "pinterest-search-agent"
    description = "Use this agent to find product trends on Pinterest."
    prompt_template = PINTEREST_AGENT_INSTRUCTIONS  # add to prompts.py

    def get_tools(self):
        return PinterestToolkit(self.config).get_tools()

# Register in build_default_registry():
def build_default_registry(config: AppConfig = None) -> SubAgentRegistry:
    ...
    registry.register(PinterestSearchSubAgent(cfg))
    ...
```

### 3. Add a new skill tool (for the orchestrator)

```python
# In research_agent/tools/research.py:

@tool
def skill_my_new_skill() -> str:
    """Describe when the orchestrator should use this skill."""
    return """
    **Skill: ...**
    Do something...
    """

# Then register it in agent.py:
research_agent = create_deep_agent(
    ...
    tools=[..., skill_my_new_skill],
    ...
)
```

---

## Environment Variables

```bash
# LLM
MODEL_PROVIDER=azure_openai         # or "google"
AZURE_OPENAI_DEPLOYMENT_NAME=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...
GOOGLE_MODEL=gemini-2.5-flash-...
GOOGLE_API_KEY=...

# Tools
ETSY_API_KEY=...                    # Etsy Open API v3
SERPAPI_API_KEY=...                 # Google Search + Google Trends
TAVILY_API_KEY=...                  # Tavily web search
REDDIT_CLIENT_ID=...                # Reddit PRAW
REDDIT_CLIENT_SECRET=...
TIKTOK_MS_TOKEN=...                 # TikTok (optional, disabled by default)

# Chainlit UI
CHAINLIT_AUTH_SECRET=...            # Secret key for session signing (required)
AUTO_LOGIN_AS_ADMIN=false           # Set to "true" to skip login and sign in as admin

# Logging
LOG_LEVEL=INFO
```

---

## Important Conventions

- **All toolkits lazy-init their tools**: `_tools` is created only on the first `get_tools()` call, then cached.
- **Backward-compat**: When renaming/moving a file, keep the old import path or provide a shim.
- **Charts**: Automatically saved to `public/charts/` with a timestamp in the filename.
- **Etsy cache**: Fetch results are cached as JSON in `output/etsy_data/` to avoid redundant API calls.
- **Sub-agent availability**: If a toolkit has no API key → `get_tools()` returns `[]` → the sub-agent is automatically skipped at build time.
- **TikTok**: Disabled by default in `build_default_registry()`. Uncomment to enable.
- **Thread persistence**: All chat threads, steps, and images are persisted in `chainlit_data.sqlite` via `SQLiteDataLayer`.
- **Auto-login**: Set `AUTO_LOGIN_AS_ADMIN=true` in `.env` to bypass the login screen (useful for local/dev deployments).
- **token.content normalization**: Some LLM backends (e.g. Anthropic) return `token.content` as a list of dicts — `_extract_text_content()` in `stream_handler.py` normalises this to a plain string before rendering.

---

## Running Locally

```bash
# Install
pip install -e .

# Run LangGraph dev server (with UI)
langgraph dev

# Run CLI
python run_cli.py

# Run Chainlit UI
chainlit run app.py
```

---

## Further Reading

- [docs/architecture.md](docs/architecture.md) — Detailed system architecture
- [docs/adding-tools.md](docs/adding-tools.md) — How to add a new toolkit
- [docs/adding-agents.md](docs/adding-agents.md) — How to add a new sub-agent
