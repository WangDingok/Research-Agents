# Adding a New Sub-agent

## Quick Checklist

1. Create (or reuse) an existing Toolkit
2. Add a prompt to `research_agent/prompts.py`
3. Create a `BaseSubAgentDef` class in `research_agent/sub_agents.py`
4. Register it in `build_default_registry()`

---

## Step 1 — Write the prompt

**File**: `research_agent/prompts.py`

```python
PINTEREST_AGENT_INSTRUCTIONS = """You are an expert at analyzing trends on Pinterest. Today is {date}.

## Task:
Find images and design ideas that are currently trending on Pinterest.

## Tools:
- `search_pinterest_trends`: Search for trends for a given keyword.

## Instructions:
1. Receive a list of keywords from the orchestrator.
2. Call search_pinterest_trends for each keyword.
3. Return the most popular boards/pins with analysis.
"""
```

**Note on {date}**: Always include `{date}` in prompt templates — it is filled in when `build()` is called.

---

## Step 2 — Create the SubAgentDef

**File**: `research_agent/sub_agents.py`

```python
from research_agent.prompts import (
    ...
    PINTEREST_AGENT_INSTRUCTIONS,  # add import
)
from research_agent.tools.pinterest import PinterestToolkit  # add import


class PinterestSearchSubAgent(BaseSubAgentDef):
    name = "pinterest-search-agent"
    description = (
        "Use this agent to find design ideas and visual trends on Pinterest. "
        "Useful when you need visual inspiration for products."
    )
    prompt_template = PINTEREST_AGENT_INSTRUCTIONS

    def get_tools(self):
        return PinterestToolkit(self.config).get_tools()
```

---

## Step 3 — Register in the registry

```python
def build_default_registry(config: AppConfig = None) -> SubAgentRegistry:
    cfg = config or default_config
    registry = SubAgentRegistry()
    
    registry.register(GoogleTrendsSubAgent(cfg))
    registry.register(TavilySearchSubAgent(cfg))
    registry.register(GoogleAISearchSubAgent(cfg))
    registry.register(EtsySearchSubAgent(cfg))
    registry.register(TwitterSearchSubAgent(cfg))
    registry.register(PinterestSearchSubAgent(cfg))  # ← add here
    
    # Disabled (uncomment to enable):
    # registry.register(TikTokSearchSubAgent(cfg))
    # registry.register(RedditSearchSubAgent(cfg))
    
    return registry
```

**Note**: If `PinterestToolkit.get_tools()` returns `[]` (no API key set), the agent is automatically skipped — no extra handling needed.

---

## Naming Conventions

| Field | Convention | Example |
|-------|-----------|--------|
| `name` | kebab-case, ending with `-agent` | `"pinterest-search-agent"` |
| Class name | PascalCase + SubAgent | `PinterestSearchSubAgent` |
| Prompt constant | `{PLATFORM}_AGENT_INSTRUCTIONS` | `PINTEREST_AGENT_INSTRUCTIONS` |

---

## Registration Order

The order of `register()` calls in `build_default_registry()` affects the order in which the orchestrator sees agents. Recommended ordering:
1. **Discovery** agents (find new trends) — Google AI Search, Twitter
2. **Validation** agents — Google Trends, Tavily, Reddit
3. **Etsy** — serves both discovery and validation
4. **Specialist** agents — TikTok, Pinterest, etc.

---

## Custom `is_available` logic

By default `is_available` returns `True` if `get_tools()` is non-empty. Override for more complex checks:

```python
class MySubAgent(BaseSubAgentDef):
    ...
    
    @property
    def is_available(self) -> bool:
        # Only available if both config and a feature flag are present
        toolkit = MyToolkit(self.config)
        return toolkit.is_available and bool(os.getenv("EXTRA_FEATURE_FLAG"))
```