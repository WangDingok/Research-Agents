"""Streaming message handler for the research agent."""

import json
import os
import re
from datetime import datetime

import chainlit as cl

from .charts import attach_charts


def _extract_image_paths(content: str) -> list[str]:
    """Extract absolute image file paths from tool output text."""
    paths = re.findall(r'(/[^\s"\']+\.(?:png|jpg|jpeg|svg))', content)
    return [p for p in paths if os.path.isfile(p)]



def _is_top_listings_result(content: str) -> dict | None:
    """Check if tool output is top listings JSON and parse it."""
    try:
        data = json.loads(content)
        if not isinstance(data, dict) or "error" in data:
            return None
        # Check if it looks like top listings: {keyword: [{title, image_url, ...}, ...]}
        for key, val in data.items():
            if isinstance(val, list) and val and isinstance(val[0], dict) and "image_url" in val[0]:
                return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None


async def _render_product_cards(listings_data: dict, parent_id: str):
    """Render Etsy top listings as product cards with images on the UI."""
    for keyword, products in listings_data.items():
        if not products:
            continue

        lines = [f"### 🏆 Top sản phẩm: {keyword}\n"]

        for i, p in enumerate(products, 1):
            img_url = p.get("image_url", "")
            title = p.get("title", "N/A")
            shop = p.get("shop_name", "N/A")
            price = p.get("price", 0)
            favs = p.get("favorites", 0)
            views = p.get("views", 0)
            url = p.get("url", "")

            # Embed image as markdown so it persists on thread resume
            if img_url:
                lines.append(f"![{title}]({img_url})\n")

            lines.append(
                f"**{i}. [{title}]({url})**\n"
                f"Shop: **{shop}** · 💰 ${price:.2f} · ❤️ {favs:,} · 👁 {views:,}\n"
            )

        msg = cl.Message(
            content="\n".join(lines),
            parent_id=parent_id,
        )
        await msg.send()


async def handle_message(message: cl.Message):
    """Handle incoming user messages and stream agent responses."""
    agent = cl.user_session.get("agent")
    config = cl.user_session.get("config")

    if not agent or not config:
        await cl.Message(content="Session error. Please refresh the page.").send()
        return

    messages = [("user", message.content)]
    run_start_time = datetime.now().timestamp()

    # Status message to hold steps during research
    status_msg = cl.Message(content="")
    await status_msg.send()

    active_steps = {}
    accumulated_tool_args = {}
    tool_call_names = {}  # track tool_call_id -> tool_name
    final_msg = None

    sub_agent_names = cl.user_session.get("sub_agent_names", [])

    try:
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
            stream_mode=["messages"],
            subgraphs=True,
            version="v2",
        ):
            is_subagent = any(s.startswith("tools:") for s in chunk["ns"])
            source = (
                next((s for s in chunk["ns"] if s.startswith("tools:")), "main")
                if is_subagent
                else "main"
            )
            agent_label = source.split(":")[-1] if is_subagent else "Main Agent"

            if chunk["type"] == "updates":
                for node_name in chunk["data"]:
                    if node_name not in {"model_request", "tools"}:
                        continue

            if chunk["type"] == "messages":
                token, _ = chunk["data"]

                # Tool call chunks
                if hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        tc_id = tc.get("id")
                        tc_name = tc.get("name")

                        if tc_name and tc_id:
                            if tc_name in sub_agent_names:
                                step_name = f"🚀 Sub-Agent: {tc_name}"
                            else:
                                step_name = f"🔧 Tool: {tc_name}"

                            step = cl.Step(
                                name=step_name,
                                type="tool",
                                show_input=True,
                                parent_id=status_msg.id,
                            )
                            step.input = ""
                            await step.send()
                            active_steps[tc_id] = step
                            accumulated_tool_args[tc_id] = ""
                            tool_call_names[tc_id] = tc_name

                        if tc.get("args"):
                            matched_id = tc_id or next(
                                (k for k in reversed(list(active_steps.keys()))),
                                None,
                            )
                            if matched_id and matched_id in accumulated_tool_args:
                                accumulated_tool_args[matched_id] += tc["args"]

                # AI content tokens
                if token.content and token.type != "tool":
                    if is_subagent:
                        step_key = f"subagent_{source}"
                        if step_key not in active_steps:
                            step = cl.Step(
                                name=f"📋 {agent_label}",
                                type="tool",
                                show_input=False,
                                parent_id=status_msg.id,
                            )
                            step.output = ""
                            await step.send()
                            active_steps[step_key] = step
                        active_steps[step_key].output += token.content
                        await active_steps[step_key].update()
                    else:
                        if final_msg is None:
                            await status_msg.update()
                            final_msg = cl.Message(content="")
                            await final_msg.send()
                        await final_msg.stream_token(token.content)

                # Tool result messages
                if token.type == "tool":
                    tool_call_id = getattr(token, "tool_call_id", None)
                    if tool_call_id and tool_call_id in active_steps:
                        step = active_steps[tool_call_id]
                        if tool_call_id in accumulated_tool_args:
                            try:
                                parsed = json.loads(
                                    accumulated_tool_args[tool_call_id]
                                )
                                step.input = json.dumps(
                                    parsed, ensure_ascii=False, indent=2
                                )
                            except (json.JSONDecodeError, TypeError):
                                step.input = accumulated_tool_args[tool_call_id]

                        content = (
                            token.content
                            if isinstance(token.content, str)
                            else json.dumps(
                                token.content, ensure_ascii=False, indent=2
                            )
                        )
                        if len(content) > 5000:
                            step.output = content[:5000] + "\n... (truncated)"
                        else:
                            step.output = content

                        await step.update()

                        # Attach chart images found in tool output.
                        # Use img.send() (not step.elements) so create_element() is
                        # called and the image persists in the DB for thread resume.
                        image_paths = _extract_image_paths(content)
                        for p in image_paths:
                            img = cl.Image(
                                name=os.path.basename(p),
                                path=p,
                                display="inline",
                            )
                            await img.send(for_id=step.id)

                        # Render product cards for get_etsy_top_listings
                        tc_name = tool_call_names.get(tool_call_id, "")
                        if tc_name == "get_etsy_top_listings":
                            listings_data = _is_top_listings_result(content)
                            if listings_data:
                                await _render_product_cards(listings_data, status_msg.id)

                # Token usage metadata
                if hasattr(token, "usage_metadata") and token.usage_metadata:
                    usage = token.usage_metadata
                    usage_text = (
                        f"Tokens → In: {usage.get('input_tokens', 0)} | "
                        f"Out: {usage.get('output_tokens', 0)} | "
                        f"Total: {usage.get('total_tokens', 0)}"
                    )
                    if is_subagent:
                        step_key = f"subagent_{source}"
                        if step_key in active_steps:
                            active_steps[step_key].output += f"\n\n_{usage_text}_"
                            await active_steps[step_key].update()

        # Finalize
        if final_msg:
            await final_msg.update()
        else:
            status_msg.content = "✅ Nghiên cứu hoàn tất"
            await status_msg.update()

        response_msg = final_msg or status_msg
        await attach_charts(response_msg, run_start_time)

    except Exception as e:
        await cl.Message(content=f"❌ Error: {str(e)}").send()
        raise
