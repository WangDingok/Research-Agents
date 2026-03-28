# Research Agents

An orchestrated multi-agent system for researching trends on Etsy and social media. Specialized sub-agents gather data from multiple platforms and synthesize findings into comprehensive reports.

## Features

- **Trend Discovery** — Find emerging niches across multiple platforms (Google AI Search, Twitter)
- **Trend Validation** — Assess real potential via Google Trends + Tavily web research
- **Etsy Analysis** — Surface top-selling products, analyze price/favorites data, auto-generate charts
- **Report Writing** — Synthesize all findings into a professional Markdown report
- **Chainlit UI** — Chat interface with conversation history and inline chart display
- **CLI Mode** — Run directly from the terminal with streaming output

## Architecture

```
User
 │
 ▼
Orchestrator Agent (LangGraph)
 │  tools: think, skill_discover_trends, skill_validate_trends,
 │          skill_find_top_products, skill_write_report
 │
 ├── google-ai-search-agent   ← Google AI Search (SerpAPI)
 ├── google-trends-agent      ← Google Trends (SerpAPI)
 ├── tavily-search-agent      ← Tavily web search
 ├── etsy-search-agent        ← Etsy Open API v3 + analysis & charts
 ├── twitter-search-agent     ← Twitter scraping (no API key required)
 ├── reddit-search-agent      ← Reddit PRAW (currently unavailable, disabled by default)
 └── tiktok-search-agent      ← TikTok (currently unavailable, disabled by default)
```

## Installation

**Requirements**: Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
# Clone the repo
git clone <repo-url>
cd Research-Agents

# Install dependencies
uv sync

# (Optional) Install Playwright for TikTok support
uv run playwright install chromium
```

## Configuration

Create a `.env` file using the template below:

```bash
# LLM Provider (choose one)
MODEL_PROVIDER=azure_openai          # or "google"

# Azure OpenAI
AZURE_OPENAI_DEPLOYMENT_NAME=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...

# Google Gemini
GOOGLE_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=...

# Search tools
ETSY_API_KEY=...                     # Etsy Open API v3
SERPAPI_API_KEY=...                  # Google Search + Google Trends
TAVILY_API_KEY=...                   # Tavily web search
REDDIT_CLIENT_ID=...                 # Reddit PRAW (currently unavailable)
REDDIT_CLIENT_SECRET=...
TIKTOK_MS_TOKEN=...                  # TikTok (currently unavailable)

# Chainlit UI
CHAINLIT_AUTH_SECRET=...             # Required for session signing
AUTO_LOGIN_AS_ADMIN=false            # Set "true" to skip the login screen

# Logging
LOG_LEVEL=INFO
```

> **Note**: If an API key is not provided, the corresponding sub-agent is automatically skipped at startup.

## Running

### Chainlit UI (recommended)

```bash
uv run chainlit run app.py
```

Open `http://localhost:8000` — chat interface with inline Etsy charts and SQLite-backed conversation history.

### CLI

```bash
python run_cli.py

# Resume a previous session
python run_cli.py --thread-id <thread_id>
```

### LangGraph Dev Server

```bash
uv run langgraph dev
```

### Docker

```bash
docker compose up
```

The app runs on port `8080`.

## Project Structure

```
Research-Agents/
├── agent.py                    # Entry point — creates research_agent for LangGraph
├── app.py                      # Chainlit UI app
├── run_cli.py                  # CLI runner
├── langgraph.json              # LangGraph deploy config
├── pyproject.toml
│
├── chainlit_app/               # Modular Chainlit UI layer
│   ├── auth.py                 # Authentication + auto-login
│   ├── charts.py               # Attaches new PNG charts after each run
│   ├── data_layer.py           # SQLiteDataLayer — persists threads/steps/elements
│   └── stream_handler.py       # Streams agent output to the UI
│
├── research_agent/             # Main package
│   ├── config.py               # AppConfig — all env vars in one place
│   ├── prompts.py              # System prompts (orchestrator + sub-agents)
│   ├── sub_agents.py           # Sub-agent declarations + build_default_registry()
│   ├── base/                   # BaseToolkit, BaseSubAgentDef, SubAgentRegistry
│   └── tools/                  # Tool implementations grouped by platform
│       ├── research.py         # TavilyToolkit + skill_* tools + think
│       ├── google.py           # GoogleAISearchToolkit, GoogleTrendsToolkit
│       ├── reddit.py           # RedditToolkit
│       ├── twitter.py          # TwitterToolkit
│       ├── tiktok.py           # TikTokTool
│       └── etsy/
│           ├── tools.py        # EtsyToolkit
│           └── analyzer.py     # EtsyTrendAnalyzer — fetch, analysis, chart generation
│
├── skills/                     # LangGraph skill definitions
├── output/
│   └── etsy_data/              # Etsy API JSON cache
└── public/charts/              # Generated chart PNG files
```

## Output

- **Charts**: Auto-saved to `public/charts/` with a timestamp in the filename
- **Etsy cache**: Fetch results cached as JSON in `output/etsy_data/` to avoid redundant API calls
- **Chat history**: Persisted in `chainlit_data.sqlite` (threads, steps, images)
- **Logs**: Saved to `output/research_run_<timestamp>.log` when running the CLI

## Extending the System

See the `docs/` folder for detailed guides:

- [`docs/adding-tools.md`](docs/adding-tools.md) — How to add a new toolkit
- [`docs/adding-agents.md`](docs/adding-agents.md) — How to add a new sub-agent
- [`docs/architecture.md`](docs/architecture.md) — Detailed system architecture
