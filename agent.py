"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""
import os
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from rich.console import Console
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

from research_agent.config import config
from research_agent.prompts import RESEARCH_WORKFLOW_TEMPLATE
from research_agent.tools.research import (
    think,
    skill_discover_trends,
    skill_validate_trends,
    skill_find_top_products,
    skill_write_report,
)
from research_agent.sub_agents import build_default_registry
from research_agent.tools.tiktok import tiktok_tools, close_tiktok_instance

console = Console()

# --- Build sub-agents from registry ---
registry = build_default_registry(config)
sub_agents = registry.build_all()
sub_agent_names = registry.get_names()

# --- Model Initialization ---
if config.model.provider == "google":
    model = init_chat_model(
        model_provider="google_genai",
        model=config.model.google_model,
        api_key=config.model.google_api_key,
        temperature=config.model.temperature,
        max_retries=config.model.max_retries,
    )
else:
    model = init_chat_model(
        model_provider="azure_openai",
        model=config.model.azure_deployment,
        api_key=config.model.azure_api_key,
        azure_endpoint=config.model.azure_endpoint,
        api_version=config.model.azure_api_version,
        temperature=config.model.temperature,
        max_retries=config.model.max_retries,
    )

final_system_prompt = RESEARCH_WORKFLOW_TEMPLATE.format(date=config.current_date)

@asynccontextmanager
async def get_checkpointer():
    """
    Note on Checkpointing:
    The factory function returns a checkpointer instance.
    When declared in langgraph.json, langgraph dev will automatically detect and use this function to manage state.
    Please note that this is a server-side entry point and is not intended to be called directly in your source code.
    """
    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
        yield saver

research_agent = create_deep_agent(
    model=model,
    tools=[
        think,
        skill_discover_trends,
        skill_validate_trends,
        skill_find_top_products,
        skill_write_report,
    ],
    # skills=['./skills/'],
    system_prompt=final_system_prompt,
    subagents=sub_agents,
    # backend=FilesystemBackend(root_dir='.'),
    checkpointer=True
)