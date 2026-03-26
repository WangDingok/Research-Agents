"""Chart/image attachment utilities."""

import glob
import os

import chainlit as cl

CHART_PATTERNS = [
    "public/charts/*.png",
    "public/charts/*.jpg",
    "public/charts/*.svg",
]


async def attach_charts(parent_msg: cl.Message, run_start_time: float):
    """Find and attach chart images created DURING this run."""
    attached: set[str] = set()
    elements = []

    for pattern in CHART_PATTERNS:
        for filepath in glob.glob(pattern, recursive=True):
            abs_path = os.path.abspath(filepath)
            if abs_path in attached:
                continue
            attached.add(abs_path)

            mtime = os.path.getmtime(abs_path)
            if mtime >= run_start_time:
                name = os.path.basename(filepath)
                elements.append(
                    cl.Image(name=name, path=abs_path, display="inline")
                )

    if elements:
        await cl.Message(
            content="📊 **Biểu đồ phân tích:**",
            elements=elements,
        ).send()
