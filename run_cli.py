import asyncio
import uuid
import logging
from datetime import datetime
import os
import argparse

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.panel import Panel
from pprint import pprint

from deepagents.backends.filesystem import FilesystemBackend

from utils import format_messages, format_message_content

from agent import (
    create_deep_agent,
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

console = Console()

LOG_TOOL_CALLS = False  

# --- Logging Setup (Logger object only) ---
# File logging will be configured in run_cli.py to avoid issues with langgraph dev.
logger = logging.getLogger('ResearchAgentLogger')
logger.setLevel(logging.INFO)

sub_agent_names = [agent["name"] for agent in sub_agents]


def setup_file_logging():
    """Sets up logging to a file in the 'output' directory."""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_dir, f'research_run_{run_timestamp}.log')

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(log_formatter)

    # Get the logger defined in agent.py and add the file handler to it
    logger = logging.getLogger('ResearchAgentLogger')
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)


async def chat_loop(agent, config):
    """Handles the user interaction loop for the research agent."""
    thread_id = config["configurable"]["thread_id"]
    console.print(Panel(f"Start new session with thread ID: [bold cyan]{thread_id}[/bold cyan]\n'exit' or 'quit' to end session.", title="Welcome", border_style="green"))

    while True:
        user_query = input("Enter your query (or 'exit' to quit): ")
        if user_query.lower() in ["exit", "quit"]:
            console.print(Panel("End session.", title="Goodbye", border_style="red"))
            break

        if not user_query.strip():
            continue

        messages = [("user", user_query)]
        logger.info("="*20 + " START NEW SESSION " + "="*20)
        logger.info(f"User query: {user_query}")
        console.print(Panel(f"Starting research for: \"{user_query}\"", title="User Request", border_style="magenta"))

        last_source = ""
        mid_line = False
        tool_id_to_name: dict = {}  # maps tool call id → human-readable name
        # Skip internal middleware steps - only show meaningful node names
        INTERESTING_NODES = {"model_request", "tools"}

        console.print(Panel("Starting research agent...", title="Executor", border_style="cyan"))
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
            stream_mode=["messages"],
            subgraphs=True,
            version="v2",
        ):
            is_subagent = any(s.startswith("tools:") for s in chunk["ns"])
            source = next((s for s in chunk["ns"] if s.startswith("tools:")), "main") if is_subagent else "main"

            if chunk["type"] == "updates":
                for node_name in chunk["data"]:
                    if node_name not in INTERESTING_NODES:
                        continue
                    if mid_line:
                        console.print()
                        mid_line = False
                    
                    console.print(f"[dim][{source}] step: {node_name}[/dim]")

            if chunk["type"] == "messages":
                token, _ = chunk["data"]

                # Tool call chunks (streaming tool invocations)
                if hasattr(token, 'tool_call_chunks') and token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        if tc.get("name"):
                            # Map tool call id → name for sub-agent display
                            if tc.get("id"):
                                tool_id_to_name[tc["id"]] = tc["name"]
                            if mid_line:
                                console.print()
                                mid_line = False
                            console.print(f"[dim][{source}] Tool call: {tc['name']}[/dim]")
                            if LOG_TOOL_CALLS:
                                logger.info(f"[{source}] Calling Tool: {tc['name']}")
                        # Args stream in chunks - only print when LOG_TOOL_CALLS enabled
                        if tc.get("args") and LOG_TOOL_CALLS:
                            print(tc["args"],end='',flush=True)
                            
                # AI token content
                if token.content and token.type != "tool":
                    logger.info(f"[{source}] Response Chunk: {token.content}")
                    if source != last_source:
                        if mid_line:
                            console.print()  # Add a newline for separation

                        # Resolve sub-agent name: look up the call ID from the namespace
                        if is_subagent:
                            call_id = source.split(":")[-1]
                            agent_label = tool_id_to_name.get(call_id, call_id)
                            console.print(f"Sub-agent: {agent_label}")
                        else:
                            console.print("Main Agent")
                        last_source = source
                        mid_line = False
                    console.print(token.content, end="", style="default")
                    mid_line = True
                
                # Token metadata — only show on chunks that carry no text content
                # (Anthropic emits an early usage event with input_tokens>0 but out=small
                #  while still streaming; skip those by requiring content to be absent)
                if hasattr(token, 'usage_metadata') and token.usage_metadata and not token.content:
                    usage = token.usage_metadata
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    total_tokens = usage.get('total_tokens', 0)
                    if input_tokens > 0 and output_tokens > 0:
                        if mid_line:
                            console.print()
                            mid_line = False
                        token_info_console = (
                            f"[dim]Tokens → In: {input_tokens} | Out: {output_tokens} | Total: {total_tokens}[/dim]"
                        )
                        token_info_log = (
                            f"Token Usage: In={input_tokens}, Out={output_tokens}, Total={total_tokens}"
                        )
                        console.print(token_info_console)
                        logger.info(token_info_log)

                # Tool results - use the classic panel display
                # if token.type == "tool":
                #     if mid_line:
                #         console.print()
                #         mid_line = False
                #     format_messages([token], sub_agent_names=sub_agent_names)

        if mid_line:
            console.print() 

        logger.info("="*20 + " END SESSION " + "="*20)
        await asyncio.sleep(0.1)


async def main():
    """
    Main function to run the research agent as a Command Line Interface (CLI) tool.
    """
    try:
        parser = argparse.ArgumentParser(description="Run the research agent CLI.")
        parser.add_argument(
            "--thread-id",
            type=str,
            help="Specify a thread ID to resume a previous session.",
        )
        args = parser.parse_args()
        console.print(Panel("Initializing agent for CLI mode with SQLite checkpointer...", title="Status", border_style="green"))

        # Set up file logging for the CLI run
        setup_file_logging()

        # Use an asynchronous context manager for the checkpointer
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as memory:
            # Create a new agent instance specifically for the CLI,
            # and inject the SQLite checkpointer instance into it.
            cli_agent = create_deep_agent(
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
                # backend=FilesystemBackend(root_dir='.', virtual_mode=False),
                checkpointer=memory
            )

            # Optional: Save the agent's graph to an image file
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            graph_path = os.path.join(output_dir, "agent_graph.png")
            try:
                with open(graph_path, "wb") as f:
                    f.write(cli_agent.get_graph().draw_mermaid_png())
                console.print(Panel(f"📊 Saved to `{graph_path}`", title="Graph", border_style="dim"))
            except Exception as e: # Could not save agent graph
                console.print(Panel(f"Could not save agent graph: {e}", title="Warning", border_style="yellow"))

            # Create a unique thread ID for this chat session
            if args.thread_id:
                thread_id = args.thread_id
                console.print(Panel(f"Resuming session with thread ID: [bold cyan]{thread_id}[/bold cyan]", title="Status", border_style="yellow"))
            else:
                thread_id = f"cli_thread_{uuid.uuid4()}"
            config = {"configurable": {"thread_id": thread_id}}

            # Start the interactive chat loop
            await chat_loop(cli_agent, config)

    finally:
        # Ensure resources are cleaned up on exit
        if tiktok_tools:
            console.print(Panel("Cleaning up TikTok resources...", title="Shutdown", border_style="dim"))
            await close_tiktok_instance()
            console.print(Panel("TikTok resources cleaned up.", title="Shutdown", border_style="dim"))

if __name__ == "__main__":
    # Run the asynchronous main function
    asyncio.run(main())
