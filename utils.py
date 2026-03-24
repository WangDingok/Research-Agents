"""Utility functions for displaying messages and prompts in Jupyter notebooks."""

import ast
import json

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def format_message_content(message, sub_agent_names=None):
    """Convert message content to displayable string."""
    parts = []
    if sub_agent_names is None:
        sub_agent_names = []
    tool_calls_processed = False

    # Handle main content
    if isinstance(message.content, str):
        # If content is a string, it might be a string-representation of a Python object
        # (e.g., from `str(my_dict)`), which escapes non-ASCII characters.
        # We try to parse it back into an object to format it correctly.
        try:
            # ast.literal_eval is a safe way to parse Python literals (dicts, lists, etc.)
            parsed_content = ast.literal_eval(message.content)
            # If successful, format it nicely as JSON with correct encoding.
            parts.append(json.dumps(parsed_content, ensure_ascii=False, indent=2))
        except (ValueError, SyntaxError):
            # It's just a regular string, not a literal, so we use it as is.
            parts.append(message.content)
    elif isinstance(message.content, list):
        # Handle complex content like tool calls (Anthropic format)
        for item in message.content:
            if item.get("type") == "text":
                parts.append(item["text"])
            elif item.get("type") == "tool_use":
                tool_name = item['name']
                if tool_name in sub_agent_names:
                    parts.append(f"\n🚀 Đang gọi Sub-Agent: {tool_name}")
                else:
                    parts.append(f"\n🔧 Lời gọi Tool: {tool_name}")
                parts.append(
                    f"   Tham số: {json.dumps(item['input'], ensure_ascii=False, indent=2)}"
                )
                parts.append(f"   ID: {item.get('id', 'N/A')}")
                tool_calls_processed = True
    elif message.content is not None:
        # For any other object (dict, etc.), format it as a pretty JSON string.
        parts.append(json.dumps(message.content, ensure_ascii=False, indent=2))
    else:
        parts.append("")  # Handle cases where content is None

    # Handle tool calls attached to the message (OpenAI format) - only if not already processed
    if (
        not tool_calls_processed
        and hasattr(message, "tool_calls")
        and message.tool_calls
    ):
        for tool_call in message.tool_calls:
            tool_name = tool_call['name']
            if tool_name in sub_agent_names:
                parts.append(f"\n🚀 Đang gọi Sub-Agent: {tool_name}")
            else:
                parts.append(f"\n🔧 Lời gọi Tool: {tool_name}")
            parts.append(
                f"   Tham số: {json.dumps(tool_call['args'], ensure_ascii=False, indent=2)}"
            )
            parts.append(f"   ID: {tool_call['id']}")

    return "\n".join(parts)


def format_messages(messages, sub_agent_names=None):
    """Format and display a list of messages with Rich formatting."""
    if sub_agent_names is None:
        sub_agent_names = []
    for m in messages:
        msg_type = m.__class__.__name__.replace("Message", "")
        content = format_message_content(m, sub_agent_names=sub_agent_names)

        token_info = ""

        try:
            if hasattr(m, "usage_metadata") and m.usage_metadata:
                usage = m.usage_metadata
                token_info = (
                    f"\n\n[dim]"
                    f"Tokens → In: {usage.get('input_tokens', 0)} | "
                    f"Out: {usage.get('output_tokens', 0)} | "
                    f"Total: {usage.get('total_tokens', 0)}"
                    f"[/dim]"
                )

            elif hasattr(m, "response_metadata") and m.response_metadata:
                usage = m.response_metadata.get("token_usage", {})
                if usage:
                    token_info = f"\n\n[dim]{usage}[/dim]"

        except Exception:
            pass

        full_content = content + token_info

        if msg_type == "Human":
            console.print(Panel(full_content, title="🧑 Human", border_style="blue"))
        elif msg_type == "Ai":
            console.print(Panel(full_content, title="🤖 Assistant", border_style="green"))
        elif msg_type == "Tool":
            console.print(Panel(full_content, title="🔧 Tool Output", border_style="yellow"))
        else:
            console.print(Panel(full_content, title=f"📝 {msg_type}", border_style="white"))


def format_message(messages, sub_agent_names=None):
    """Alias for format_messages for backward compatibility."""
    return format_messages(messages, sub_agent_names=sub_agent_names)


def show_prompt(prompt_text: str, title: str = "Prompt", border_style: str = "blue"):
    """Display a prompt with rich formatting and XML tag highlighting.

    Args:
        prompt_text: The prompt string to display
        title: Title for the panel (default: "Prompt")
        border_style: Border color style (default: "blue")
    """
    # Create a formatted display of the prompt
    formatted_text = Text(prompt_text)
    formatted_text.highlight_regex(r"<[^>]+>", style="bold blue")  # Highlight XML tags
    formatted_text.highlight_regex(
        r"##[^#\n]+", style="bold magenta"
    )  # Highlight headers
    formatted_text.highlight_regex(
        r"###[^#\n]+", style="bold cyan"
    )  # Highlight sub-headers

    # Display in a panel for better presentation
    console.print(
        Panel(
            formatted_text,
            title=f"[bold green]{title}[/bold green]",
            border_style=border_style,
            padding=(1, 2),
        )
    )
