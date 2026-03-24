import asyncio
import uuid
import logging
from datetime import datetime
import os

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console
from rich.panel import Panel

from utils import format_messages, format_message_content

from agent import (
    create_deep_agent,
    model,
    think,
    final_system_prompt,
    sub_agents,
    close_tiktok_instance,
    tiktok_tools,
)

console = Console()

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

        processed_message_count = 0
        console.print(Panel("Starting research agent...", title="Excutor", border_style="cyan"))
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
            stream_mode="values",
        ):
            if "messages" in chunk:
                new_messages = chunk["messages"][processed_message_count:]
                for msg in new_messages:
                    msg_type = msg.__class__.__name__.replace("Message", "")
                    content = format_message_content(msg, sub_agent_names=sub_agent_names)
                    log_message = f"===== {msg_type} new =====\n{content}"
                    logger.info(log_message)

                processed_message_count = len(chunk["messages"])
                format_messages(new_messages, sub_agent_names=sub_agent_names)

        logger.info("="*20 + " END SESSION " + "="*20)
        await asyncio.sleep(0.1)


async def main():
    """
    Main function to run the research agent as a Command Line Interface (CLI) tool.
    """
    try:
        console.print(Panel("Initializing agent for CLI mode with SQLite checkpointer...", title="Status", border_style="green"))

        # Set up file logging for the CLI run
        setup_file_logging()

        # Use an asynchronous context manager for the checkpointer
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as memory:
            # Create a new agent instance specifically for the CLI,
            # and inject the SQLite checkpointer instance into it.
            cli_agent = create_deep_agent(
                model=model,
                tools=[think],
                system_prompt=final_system_prompt,
                subagents=sub_agents,
                checkpointer=memory,
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
            config = {"configurable": {"thread_id": f"cli_thread_{uuid.uuid4()}"}}

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
