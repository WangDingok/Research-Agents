"""Chainlit UI for the Deep Research Agent.

Thin entry point — imports modular components from chainlit_app/.
"""

import aiosqlite
import chainlit as cl
import chainlit.data as cl_data
from chainlit.types import ThreadDict
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from deepagents import create_deep_agent
from agent import (
    model,
    think,
    skill_discover_trends,
    skill_validate_trends,
    skill_find_top_products,
    skill_write_report,
    final_system_prompt,
    sub_agents,
    close_tiktok_instance,
    tiktok_tools,
)

from chainlit_app.data_layer import SQLiteDataLayer
from chainlit_app.auth import auth_callback  # noqa: F401 — registers decorator
from chainlit_app.stream_handler import handle_message

sub_agent_names = [agent["name"] for agent in sub_agents]

# ── Data layer ───────────────────────────────────────────────────────
cl_data._data_layer = SQLiteDataLayer()

# ── Checkpointer (singleton) ────────────────────────────────────────
_checkpointer = None


async def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect("checkpoints.sqlite")
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer


# ── Session helpers ──────────────────────────────────────────────────

async def _init_agent_session(langgraph_thread_id: str):
    """Shared setup for new and resumed sessions."""
    checkpointer = await get_checkpointer()
    agent = create_deep_agent(
        model=model,
        tools=[
            think,
            skill_discover_trends,
            skill_validate_trends,
            skill_find_top_products,
            skill_write_report,
        ],
        system_prompt=final_system_prompt,
        subagents=sub_agents,
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": langgraph_thread_id}}
    cl.user_session.set("agent", agent)
    cl.user_session.set("config", config)
    cl.user_session.set("langgraph_thread_id", langgraph_thread_id)
    cl.user_session.set("sub_agent_names", sub_agent_names)


# ── Lifecycle hooks ──────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    chainlit_thread_id = cl.context.session.thread_id
    langgraph_thread_id = f"lg_{chainlit_thread_id}"
    await _init_agent_session(langgraph_thread_id)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    chainlit_thread_id = thread["id"]
    langgraph_thread_id = f"lg_{chainlit_thread_id}"
    await _init_agent_session(langgraph_thread_id)


@cl.on_message
async def on_message(message: cl.Message):
    await handle_message(message)


@cl.on_chat_end
async def on_chat_end():
    if tiktok_tools:
        try:
            await close_tiktok_instance()
        except Exception:
            pass
