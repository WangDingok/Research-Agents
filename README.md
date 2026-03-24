# Research Agents

This example demonstrates an autonomous, multi-agent research system built with Deepagents and LangGraph. The agent orchestrates a team of specialized sub-agents to perform in-depth research on a user-provided topic, synthesizing information from various sources to identify emerging trends.

## Architecture

The system uses a hierarchical architecture consisting of a main orchestrator agent and several specialized sub-agents.

### Orchestrator Agent

The main agent acts as a project manager. It follows a predefined workflow to break down the research request into stages and delegate tasks to the appropriate sub-agents.

The workflow consists of the following stages:
1.  **Trend Discovery**: Gather a broad list of potential trends from various sources.
2.  **Filtering & Evaluation**: Further analyze the found trends to verify their sustainability and community interest.
3.  **Exploitation & Inspiration**: Gather detailed information on validated trends for specific purposes (e.g., product design).
4.  **Synthesis & Reporting**: Compile all findings into a coherent final report for the user.

### Sub-Agents

Each sub-agent is designed to perform a specific task using specialized tools:

-   **`google-trends-agent`**: Analyzes Google search trends, identifies keywords with surging search volume, and assesses their stability.
-   **`tavily-search-agent`**: Performs deep web searches to find articles, blogs, and forum discussions related to a topic.
-   **`twitter-search-agent`**: Identifies trending topics and keywords on Twitter.
-   **`google-ai-search-agent`**: Uses Google's AI-powered search to get an overview and identify sub-topics.

The following agents are also available and can be enabled in `agent.py`:
-   **`reddit-search-agent`**: Researches discussion levels and virality on Reddit.
-   **`etsy-search-agent`**: Analyzes product trends on Etsy.
-   **`tiktok-search-agent`**: Assesses the virality of keywords on TikTok.

## Quickstart

### Prerequisites

- Python 3.8+
- uv (package manager)

### 1. Installation

Ensure you are in the `research_agents` directory:
```bash
cd research_agents
```

Install packages:

```bash
uv sync
```

Set your API keys in your environment:

```bash
export ANTHROPIC_API_KEY=your_anthropic_api_key_here  # Required for Claude model
export GOOGLE_API_KEY=your_google_api_key_here        # Required for Gemini model ([get one here](https://ai.google.dev/gemini-api/docs))
export TAVILY_API_KEY=your_tavily_api_key_here        # Required for web search ([get one here](https://www.tavily.com/)) with a generous free tier
export LANGSMITH_API_KEY=your_langsmith_api_key_here  # [LangSmith API key](https://smith.langchain.com/settings) (free to sign up)
```

## Usage Options

You can run this example in two ways:

### Option 1: Jupyter Notebook

Run the interactive notebook to step through the research agent:

```bash
uv run jupyter notebook research_agent.ipynb
```

### Option 2: LangGraph Server

Run a local [LangGraph server](https://langchain-ai.github.io/langgraph/tutorials/langgraph-platform/local-server/) with a web interface:

```bash
uv run langgraph dev
```

LangGraph server will open a new browser window with the Studio interface, which you can submit your search query to:

<img width="2869" height="1512" alt="Screenshot 2025-11-17 at 11 42 59 AM" src="https://github.com/user-attachments/assets/03090057-c199-42fe-a0f7-769704c2124b" />

You can also connect the LangGraph server to a [UI specifically designed for deepagents](https://github.com/langchain-ai/deep-agents-ui):

```bash
git clone https://github.com/langchain-ai/deep-agents-ui.git
cd deep-agents-ui
yarn install
yarn dev
```

Then follow the instructions in the [deep-agents-ui README](https://github.com/langchain-ai/deep-agents-ui?tab=readme-ov-file#connecting-to-a-langgraph-server) to connect the UI to the running LangGraph server.

This provides a user-friendly chat interface and visualization of files in state.

<img width="2039" height="1495" alt="Screenshot 2025-11-17 at 1 11 27 PM" src="https://github.com/user-attachments/assets/d559876b-4c90-46fb-8e70-c16c93793fa8" />

## 📚 Resources

- **[Deep Research Course](https://academy.langchain.com/courses/deep-research-with-langgraph)** - Full course on deep research with LangGraph

### Custom Model

By default, `deepagents` uses `"claude-sonnet-4-5-20250929"`. You can customize this by passing any [LangChain model object](https://python.langchain.com/docs/integrations/chat/). See the Deep Agents package [README](https://github.com/langchain-ai/deepagents?tab=readme-ov-file#model) for more details.

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

# Using Claude
model = init_chat_model(model="anthropic:claude-sonnet-4-5-20250929", temperature=0.0)

# Using Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview")

agent = create_deep_agent(
    model=model,
)
```

### Custom Instructions

The deep research agent uses custom instructions defined in `research_agent/prompts.py` that complement (rather than duplicate) the default middleware instructions. You can modify these in any way you want.

| Instruction Set | Purpose |
|----------------|---------|
| `RESEARCH_WORKFLOW_INSTRUCTIONS` | Defines the 5-step research workflow: save request → plan with TODOs → delegate to sub-agents → synthesize → respond. Includes research-specific planning guidelines like batching similar tasks and scaling rules for different query types. |
| `SUBAGENT_DELEGATION_INSTRUCTIONS` | Provides concrete delegation strategies with examples: simple queries use 1 sub-agent, comparisons use 1 per element, multi-faceted research uses 1 per aspect. Sets limits on parallel execution (max 3 concurrent) and iteration rounds (max 3). |
| `RESEARCHER_INSTRUCTIONS` | Guides individual research sub-agents to conduct focused web searches. Includes hard limits (2-3 searches for simple queries, max 5 for complex), emphasizes using `think_tool` after each search for strategic reflection, and defines stopping criteria. |

### Custom Tools

The deep research agent adds the following custom tools beyond the built-in deepagent tools. You can also use your own tools, including via MCP servers. See the Deep Agents package [README](https://github.com/langchain-ai/deepagents?tab=readme-ov-file#mcp) for more details.
