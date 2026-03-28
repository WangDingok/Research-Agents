# System Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                     agent.py                            │
│  research_agent = create_deep_agent(                    │
│    model=LLM,                                           │
│    tools=[think, skill_discover_trends, ...],  ← orchestrator tools
│    system_prompt=RESEARCH_WORKFLOW_TEMPLATE,            │
│    subagents=registry.build_all(),             ← sub-agents
│    checkpointer=True                                    │
│  )                                                      │
└─────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
  Orchestrator tools           Sub-agents (deepagents)
  ─────────────────            ───────────────────────
  think                        google-ai-search-agent
  skill_discover_trends        google-trends-agent
  skill_validate_trends        tavily-search-agent
  skill_find_top_products      etsy-search-agent
  skill_write_report           twitter-search-agent
                               [reddit-search-agent]  ← disabled
                               [tiktok-search-agent]  ← disabled
```

## Base Classes

### BaseToolkit (`research_agent/base/base.py`)

Standard pattern for all toolkits:

```python
class BaseToolkit(ABC):
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(...)
    
    @abstractmethod
    def get_tools(self) -> list: ...
    
    @property
    def is_available(self) -> bool: return True
```

Each toolkit:
- Receives `config: AppConfig` (or the relevant sub-config)
- Lazy-inits tools: creates once and caches in `self._tools`
- Checks `is_available` based on whether an API key is present

### BaseSubAgentDef (`research_agent/base/base.py`)

```python
class BaseSubAgentDef(ABC):
    name: str               # Agent ID, e.g. "etsy-search-agent"
    description: str        # Description so orchestrator knows when to use it
    prompt_template: str    # System prompt, supports {date}
    
    def get_tools(self) -> list: ...   # abstract
    def build(self) -> dict | None:    # Builds dict for create_deep_agent()
```

### SubAgentRegistry (`research_agent/base/base.py`)

```python
registry = SubAgentRegistry()
registry.register(GoogleAISearchSubAgent(cfg))
registry.register(EtsySearchSubAgent(cfg))
sub_agents = registry.build_all()   # skips agents with missing API keys
```

## Config System (`research_agent/config.py`)

Hierarchical structure:

```
AppConfig
├── model: ModelConfig      (Azure OpenAI / Google Gemini)
├── etsy: EtsyConfig        (ETSY_API_KEY)
├── google: GoogleConfig    (SERPAPI_API_KEY)  
├── tavily: TavilyConfig    (TAVILY_API_KEY)
├── reddit: RedditConfig    (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
├── tiktok: TikTokConfig    (TIKTOK_MS_TOKEN)
└── twitter: TwitterConfig  (no API key needed — scraping-based)
```

Each config class has an `is_available` property to check whether credentials are set.

Singleton: `from research_agent.config import config`

## Etsy Analysis Pipeline

The `EtsyToolkit` in `tools/etsy/tools.py` calls `EtsyTrendAnalyzer` in `tools/etsy/analyzer.py`:

```
search_etsy_trends_by_keyword(keywords, days_back)
    │
    ▼
EtsyTrendAnalyzer.run_analysis(keywords, days_back)
    │
    ├─ keywords=[]  →  _fetch_listings(None)  →  _analyze_data()  →  _generate_general_dashboard()
    │               (general market)             (dashboard PNG)
    │
    └─ keywords=[...]  →  foreach kw: _fetch_listings(kw)  →  _analyze_data()
                        →  _generate_keyword_dashboard()  (per-keyword PNG)
                        →  _generate_comparison_charts()  (comparison + opportunity matrix PNGs)
```

**Cache**: Etsy API responses are cached as JSON in `output/etsy_data/listings_tshirts_{keyword}_{days}days.json`. If the file exists, the API call is skipped.

**Charts**: PNG files are saved to `public/charts/` with a timestamp. Paths are returned in the JSON output so the UI can display them.

## Skill Tools (Orchestrator)

`skill_*` tools in `tools/research.py` are "meta-instructions" — they return text that tells the orchestrator how to coordinate sub-agents:

```
skill_discover_trends()    → instructs: use google-ai-search + twitter + etsy in parallel
skill_validate_trends()    → instructs: use google-trends + tavily + etsy in parallel
skill_find_top_products()  → instructs: use etsy + google-ai-search + tavily in parallel
skill_write_report()       → instructs: standard report formatting rules
```

## Outputs and Artifacts

| Type | Location | Description |
|------|----------|-------------|
| Etsy cache | `output/etsy_data/*.json` | API response cache |
| Charts | `public/charts/*.png` | Matplotlib charts from analyzer |
| Checkpoints | `checkpoints.sqlite` | LangGraph conversation state |
| Thread data | `chainlit_data.sqlite` | Chainlit threads, steps, elements (SQLiteDataLayer) |

---

## Chainlit UI Layer (`chainlit_app/`)

`app.py` is the thin entry point. All UI logic lives in `chainlit_app/`:

```
app.py
  │  on_chat_start  → _init_agent_session()   creates agent + config, stores in user_session
  │  on_chat_resume → _init_agent_session()   re-creates agent for existing thread
  │  on_message     → handle_message()        delegates to stream_handler
  │
  ├── chainlit_app/stream_handler.py   handle_message()
  │     streams agent.astream() chunks to UI:
  │       • tool_call_chunks  → cl.Step ("🔧 Tool: ...")  shown as collapsible steps
  │       • is_subagent       → cl.Step ("📋 sub-agent-name")  sub-agent output
  │       • AI text tokens    → cl.Message  streamed to final answer
  │       • tool result       → step.output  (truncated at 5 000 chars)
  │       • image paths       → cl.Image attached to step
  │       • usage_metadata    → appended to sub-agent step output
  │
  ├── chainlit_app/data_layer.py   SQLiteDataLayer
  │     Implements BaseDataLayer for thread persistence:
  │       • create/update/delete_step  → stored in steps table
  │       • create_element            → chart images stored with /public/charts/ URL
  │       • list_threads / get_thread → rebuilds ThreadDict from DB on resume
  │       • _filter_steps_for_resume  → strips empty/status-only messages
  │                                     clears parentId so tool steps appear top-level
  │
  ├── chainlit_app/auth.py
  │     @cl.header_auth_callback  → auto-login as admin (AUTO_LOGIN_AS_ADMIN=true)
  │     @cl.password_auth_callback → normal username/password login
  │
  └── chainlit_app/charts.py   attach_charts()
        scans public/charts/*.png for files newer than run_start_time
        attaches them as cl.Image elements after each completed run
```

### Resuming a Thread

When a user opens an old thread:
1. `on_chat_resume` re-creates the agent with the same `langgraph_thread_id`
2. Chainlit calls `data_layer.get_thread()` → `_load_thread_steps()`
3. `_filter_steps_for_resume` keeps only `tool` and `*message` type steps, drops empty containers
4. `_normalize_step` sets `parentId = None` for all kept steps so they render at root level
5. Sub-agent and tool steps that were nested under a status message become visible again