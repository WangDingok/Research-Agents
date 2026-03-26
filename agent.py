"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""
import os
from pathlib import Path
from datetime import date, datetime
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from tabnanny import check
import uuid
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from rich.console import Console
from rich.panel import Panel
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from dotenv import load_dotenv

from research_agent.prompts import (
    RESEARCH_WORKFLOW_TEMPLATE,
    GOOGLE_AI_SEARCH_AGENT_INSTRUCTIONS,
    GOOGLE_TRENDS_AGENT_INSTRUCTIONS,
    TAVILY_SEARCH_AGENT_INSTRUCTIONS,
    TIKTOK_SEARCH_AGENT_INSTRUCTIONS,
    ETSY_SEARCH_AGENT_INSTRUCTIONS,
    REDDIT_SEARCH_AGENT_INSTRUCTIONS,
    TWITTER_SEARCH_AGENT_INSTRUCTIONS,
)
from research_agent.research_tools import (
    tavily_search, think, tavily_search_async,
    skill_discover_trends,
    skill_validate_trends,
    skill_find_top_products,
    skill_write_report,
)
from research_agent.google_tools import google_ai_search_tools, google_trends_tools
from research_agent.tiktok_tools import tiktok_tools, close_tiktok_instance
from research_agent.reddit_tools import reddit_tools
from research_agent.etsy_tools import etsy_tools
from research_agent.twitter_tools import twitter_tools
from utils import format_messages, format_message_content

load_dotenv()
console = Console()

# --- Agent Configuration ---
current_date = datetime.now().strftime("%Y-%m-%d")

# --- Sub-agent Definitions ---
google_ai_search_sub_agent = {
    "name": "google-ai-search-agent",
    "description": "Sử dụng agent này để thực hiện một tìm kiếm ban đầu bằng chế độ AI của Google. Nó rất hữu ích để có được một bản tóm tắt tổng quan và xác định các ngách hoặc chủ đề con tiềm năng từ một truy vấn của người dùng.",
    "system_prompt": GOOGLE_AI_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": google_ai_search_tools,
}

google_trends_sub_agent = {
    "name": "google-trends-agent",
    "description": "Sử dụng agent này để xác minh các xu hướng trên Google Trends.",
    "system_prompt": GOOGLE_TRENDS_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": google_trends_tools,
}

tavily_search_sub_agent = {
    "name": "tavily-search-agent",
    "description": "Sử dụng agent này để thực hiện nghiên cứu sâu trên web về một danh sách niche. Nó sẽ xác minh mức độ quan tâm của công chúng và truyền thông.",
    "system_prompt": TAVILY_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search, tavily_search_async, think],
}

# tiktok_search_sub_agent = {
#     "name": "tiktok-search-agent",
#     "description": "Sử dụng agent này để phân tích mức độ lan truyền của một danh sách niche trên TikTok.",
#     "system_prompt": TIKTOK_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
#     "tools": tiktok_tools,
# }

# To add Reddit and Etsy agents, uncomment their definitions and add them to the `sub_agents` list.
# reddit_search_sub_agent = {
#     "name": "reddit-search-agent",
#     "description": "Sử dụng agent này để nghiên cứu mức độ thảo luận và lan truyền của một niche trên Reddit, nhằm tìm kiếm các xu hướng văn hóa và cộng đồng.",
#     "system_prompt": REDDIT_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
#     "tools": reddit_tools,
# }

etsy_search_sub_agent = {
    "name": "etsy-search-agent",
    "description": "Sử dụng agent này để phân tích sâu về thị trường ngách trên Etsy. Nó cung cấp dữ liệu về giá cả, mức độ phổ biến (lượt thích, lượt xem), tỷ lệ sản phẩm bán chạy và các từ khóa liên quan để đánh giá tiềm năng kinh doanh của một niche.",
    "system_prompt": ETSY_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": etsy_tools,
}

twitter_search_sub_agent = {
    "name": "twitter-search-agent",
    "description": "Sử dụng agent này để nghiên cứu các chủ đề và niche đang thịnh hành trên Twitter.",
    "system_prompt": TWITTER_SEARCH_AGENT_INSTRUCTIONS.format(date=current_date),
    "tools": twitter_tools,
}

sub_agents = [
    google_trends_sub_agent, 
    tavily_search_sub_agent,
    #tiktok_search_sub_agent,
    google_ai_search_sub_agent,
    # reddit_search_sub_agent,
    etsy_search_sub_agent,
    twitter_search_sub_agent,
]

# Filter out agents with no available tools
sub_agents = [agent for agent in sub_agents if agent.get("tools")]

sub_agent_names = [agent["name"] for agent in sub_agents]

# --- Global Agent Initialization for LangGraph UI ---
model = init_chat_model(
    model_provider="azure_openai",
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.0,
    max_retries=3
)

final_system_prompt = RESEARCH_WORKFLOW_TEMPLATE.format(date=current_date)

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