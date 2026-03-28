"""Deep Research Agent Example.

This module demonstrates building a research agent using the deepagents package
with custom tools for web search and strategic thinking.
"""

from research_agent.config import BaseConfig, AppConfig, config
from research_agent.base.base import BaseToolkit, BaseSubAgentDef, SubAgentRegistry
from research_agent.prompts import *
from research_agent.tools.research import *
