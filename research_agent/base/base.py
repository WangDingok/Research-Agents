"""Base classes for Agents and Tools with inheritance support.

Provides:
- BaseToolkit: Base class for grouping related tools with shared config/state
- BaseSubAgentDef: Base class for defining sub-agent configurations
- SubAgentRegistry: Registry to collect and manage sub-agents

Usage:
    # Creating a new toolkit (group of tools):
    class MyToolkit(BaseToolkit):
        def __init__(self, config):
            super().__init__(config)
            # setup shared state...
        
        def get_tools(self):
            return [self.my_tool]
        
        @tool
        def my_tool(self, query: str) -> str:
            ...
    
    # Creating a new sub-agent definition:
    class MySubAgent(BaseSubAgentDef):
        name = "my-search-agent"
        description = "Does X research"
        prompt_template = "You are ... Today is {date}."
        
        def get_tools(self):
            return MyToolkit(self.config).get_tools()
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from research_agent.config import BaseConfig, AppConfig, config as default_config

logger = logging.getLogger("ResearchAgentLogger")


class BaseToolkit(ABC):
    """Base class for a group of related tools sharing config and state.
    
    Subclass this to create a toolkit (e.g., EtsyToolkit, GoogleToolkit).
    Each toolkit encapsulates its tools + any shared clients/state.
    """

    def __init__(self, config: BaseConfig = None):
        self.config = config or default_config
        self.logger = logging.getLogger(f"ResearchAgentLogger.{self.__class__.__name__}")

    @abstractmethod
    def get_tools(self) -> list:
        """Return list of langchain @tool functions this toolkit provides."""
        ...

    @property
    def is_available(self) -> bool:
        """Override to check if this toolkit's dependencies (API keys, etc.) are met."""
        return True


class BaseSubAgentDef(ABC):
    """Base class for sub-agent definitions.
    
    Subclass this to define a new sub-agent with its prompt, tools, and config.
    Provides a standard interface that agent.py can consume.
    """

    name: str = ""
    description: str = ""
    prompt_template: str = ""  # Use {date} placeholder

    def __init__(self, config: AppConfig = None):
        self.config = config or default_config

    @abstractmethod
    def get_tools(self) -> list:
        """Return the tools this sub-agent should have access to."""
        ...

    @property
    def is_available(self) -> bool:
        """Override to check if this sub-agent can be used (e.g., API keys present)."""
        tools = self.get_tools()
        return bool(tools)

    def build(self) -> Optional[Dict[str, Any]]:
        """Build the sub-agent dict consumed by create_deep_agent().
        
        Returns None if the agent is not available (missing tools/config).
        """
        if not self.is_available:
            logger.warning(f"Sub-agent '{self.name}' is not available (missing config/tools). Skipping.")
            return None

        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.prompt_template.format(date=self.config.current_date),
            "tools": self.get_tools(),
        }


class SubAgentRegistry:
    """Registry that collects sub-agent definitions and builds them.
    
    Usage:
        registry = SubAgentRegistry()
        registry.register(GoogleAISearchSubAgent())
        registry.register(EtsySubAgent())
        
        sub_agents = registry.build_all()       # List of dicts for create_deep_agent
        sub_agent_names = registry.get_names()   # List of active agent names
    """

    def __init__(self):
        self._agents: List[BaseSubAgentDef] = []

    def register(self, agent_def: BaseSubAgentDef):
        """Register a sub-agent definition."""
        self._agents.append(agent_def)

    def build_all(self) -> List[Dict[str, Any]]:
        """Build all registered sub-agents, skipping unavailable ones."""
        results = []
        for agent_def in self._agents:
            built = agent_def.build()
            if built:
                results.append(built)
        return results

    def get_names(self) -> List[str]:
        """Get names of all available sub-agents."""
        return [a.name for a in self._agents if a.is_available]
