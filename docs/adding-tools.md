# Adding a New Toolkit / Tool

## Quick Checklist

1. Create `research_agent/tools/<platform>.py`
2. Implement a class extending `BaseToolkit`
3. Add config to `research_agent/config.py`
4. Export in `research_agent/tools/__init__.py`
5. Create a sub-agent in `research_agent/sub_agents.py`
6. Add a prompt to `research_agent/prompts.py`
7. Add the env var to `.env`

---

## Step 1 — Create the toolkit file

**File**: `research_agent/tools/pinterest.py`

```python
import json
import asyncio
from langchain_core.tools import tool
from research_agent.base.base import BaseToolkit
from research_agent.config import AppConfig, config as default_config


class PinterestToolkit(BaseToolkit):
    """Toolkit for Pinterest trend analysis."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.pinterest  # PinterestConfig from AppConfig
        self._api_key = cfg.api_key
        self._tools = None

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        if not self.is_available:
            self._tools = []
            return self._tools

        api_key = self._api_key
        logger = self.logger

        @tool
        async def search_pinterest_trends(keyword: str) -> str:
            """Search for trends on Pinterest for a given keyword.
            
            Args:
                keyword: The keyword to search for.
            
            Returns:
                JSON string containing results.
            """
            try:
                # ... logic here ...
                result = {"keyword": keyword, "results": []}
                logger.info(f"Pinterest results for '{keyword}': {result}")
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)})

        self._tools = [search_pinterest_trends]
        return self._tools
```

---

## Step 2 — Add Config

**File**: `research_agent/config.py`

```python
@dataclass
class PinterestConfig(BaseConfig):
    """Pinterest API configuration."""
    
    api_key: str = field(default_factory=lambda: os.getenv("PINTEREST_API_KEY", ""))

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
```

And add it to `AppConfig`:

```python
@dataclass
class AppConfig:
    ...
    pinterest: PinterestConfig = field(default_factory=PinterestConfig)
```

---

## Step 3 — Export in tools/__init__.py

**File**: `research_agent/tools/__init__.py`

```python
from research_agent.tools.pinterest import PinterestToolkit

__all__ = [
    ...
    "PinterestToolkit",
]
```

---

## Step 4 — Add to .env

```bash
PINTEREST_API_KEY=your_api_key_here
```

---

## Pattern for scraping-based tools (no API key)

Example: `TwitterToolkit` — no auth required:

```python
class MyScrapingToolkit(BaseToolkit):
    
    @property
    def is_available(self) -> bool:
        return True  # Always available, no API key needed
    
    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        # No is_available check needed
        ...
```

---

## Pattern for complex async tools (e.g. TikTok)

When browser sessions or long-lived connections are needed:

```python
_tool_instance = None

def get_tool_instance():
    global _tool_instance
    if _tool_instance is None:
        try:
            token = os.environ.get("MY_TOKEN")
            if not token:
                raise ValueError("MY_TOKEN not set")
            _tool_instance = MyTool(token)
        except Exception as e:
            logger.warning(f"Could not init tool: {e}")
    return _tool_instance

@tool
async def my_tool_func(query: str) -> str:
    """..."""
    instance = get_tool_instance()
    if not instance:
        return json.dumps({"error": "Tool not available"})
    result = await instance.search(query)
    return json.dumps(result)

# Collect tools
if get_tool_instance() is not None:
    my_tools = [my_tool_func]
else:
    my_tools = []
```

---

## Adding a Skill Tool for the Orchestrator

Skill tools are meta-instructions in `research_agent/tools/research.py`. They return text that instructs the orchestrator how to coordinate sub-agents:

```python
@tool
def skill_research_competitors() -> str:
    """Skill for competitive analysis: how to find and compare competitor shops.
    
    Call when the user wants to know what competitors are doing.
    """
    return """
**Skill: Competitive Analysis**

Launch SIMULTANEOUSLY:
1. `etsy-search-agent` — Use get_etsy_top_listings to find top shops.
2. `tavily-search-agent` — Find additional info about those shops.
"""
```

Then register it in `agent.py`:

```python
from research_agent.tools.research import ..., skill_research_competitors

research_agent = create_deep_agent(
    ...
    tools=[..., skill_research_competitors],
    ...
)
```