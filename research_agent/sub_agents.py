"""Sub-agent definitions using BaseSubAgentDef.

Each sub-agent is a class inheriting from BaseSubAgentDef,
making it easy to add new agents by just creating a new class.
"""

from research_agent.base.base import BaseSubAgentDef, SubAgentRegistry
from research_agent.config import AppConfig, config as default_config
from research_agent.prompts import (
    GOOGLE_AI_SEARCH_AGENT_INSTRUCTIONS,
    GOOGLE_TRENDS_AGENT_INSTRUCTIONS,
    TAVILY_SEARCH_AGENT_INSTRUCTIONS,
    TIKTOK_SEARCH_AGENT_INSTRUCTIONS,
    ETSY_SEARCH_AGENT_INSTRUCTIONS,
    REDDIT_SEARCH_AGENT_INSTRUCTIONS,
    TWITTER_SEARCH_AGENT_INSTRUCTIONS,
)
from research_agent.tools.google import GoogleAISearchToolkit, GoogleTrendsToolkit
from research_agent.tools.etsy import EtsyToolkit
from research_agent.tools.twitter import TwitterToolkit
from research_agent.tools.reddit import RedditToolkit
from research_agent.tools.research import TavilyToolkit, think
from research_agent.tools.tiktok import tiktok_tools, close_tiktok_instance


# --- Sub-agent Definitions ---

class GoogleAISearchSubAgent(BaseSubAgentDef):
    name = "google-ai-search-agent"
    description = (
        "Sử dụng agent này để thực hiện một tìm kiếm ban đầu bằng chế độ AI của Google. "
        "Nó rất hữu ích để có được một bản tóm tắt tổng quan và xác định các ngách hoặc "
        "chủ đề con tiềm năng từ một truy vấn của người dùng."
    )
    prompt_template = GOOGLE_AI_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return GoogleAISearchToolkit(self.config).get_tools()


class GoogleTrendsSubAgent(BaseSubAgentDef):
    name = "google-trends-agent"
    description = "Sử dụng agent này để xác minh các xu hướng trên Google Trends."
    prompt_template = GOOGLE_TRENDS_AGENT_INSTRUCTIONS

    def get_tools(self):
        return GoogleTrendsToolkit(self.config).get_tools()


class TavilySearchSubAgent(BaseSubAgentDef):
    name = "tavily-search-agent"
    description = (
        "Sử dụng agent này để thực hiện nghiên cứu sâu trên web về một danh sách niche. "
        "Nó sẽ xác minh mức độ quan tâm của công chúng và truyền thông."
    )
    prompt_template = TAVILY_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return TavilyToolkit(self.config).get_tools() + [think]


class TikTokSearchSubAgent(BaseSubAgentDef):
    name = "tiktok-search-agent"
    description = "Sử dụng agent này để phân tích mức độ lan truyền của một danh sách niche trên TikTok."
    prompt_template = TIKTOK_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return tiktok_tools


class RedditSearchSubAgent(BaseSubAgentDef):
    name = "reddit-search-agent"
    description = (
        "Sử dụng agent này để nghiên cứu mức độ thảo luận và lan truyền của một niche trên Reddit, "
        "nhằm tìm kiếm các xu hướng văn hóa và cộng đồng."
    )
    prompt_template = REDDIT_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return RedditToolkit(self.config).get_tools()


class EtsySearchSubAgent(BaseSubAgentDef):
    name = "etsy-search-agent"
    description = (
        "Sử dụng agent này để phân tích sâu về thị trường ngách trên Etsy. Nó cung cấp dữ liệu "
        "về giá cả, mức độ phổ biến (lượt thích, lượt xem), tỷ lệ sản phẩm bán chạy và các từ khóa "
        "liên quan để đánh giá tiềm năng kinh doanh của một niche."
    )
    prompt_template = ETSY_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return EtsyToolkit(self.config).get_tools()


class TwitterSearchSubAgent(BaseSubAgentDef):
    name = "twitter-search-agent"
    description = "Sử dụng agent này để nghiên cứu các chủ đề và niche đang thịnh hành trên Twitter."
    prompt_template = TWITTER_SEARCH_AGENT_INSTRUCTIONS

    def get_tools(self):
        return TwitterToolkit(self.config).get_tools()


def build_default_registry(config: AppConfig = None) -> SubAgentRegistry:
    """Build the default registry with all sub-agents.
    
    To add a new sub-agent, just create a new class above and register it here.
    Unavailable agents (missing API keys/tools) are automatically skipped.
    """
    cfg = config or default_config
    registry = SubAgentRegistry()
    
    registry.register(GoogleTrendsSubAgent(cfg))
    registry.register(TavilySearchSubAgent(cfg))
    # registry.register(TikTokSearchSubAgent(cfg))  # Uncomment when TikTok is needed
    registry.register(GoogleAISearchSubAgent(cfg))
    # registry.register(RedditSearchSubAgent(cfg))   # Uncomment when Reddit is needed
    registry.register(EtsySearchSubAgent(cfg))
    registry.register(TwitterSearchSubAgent(cfg))
    
    return registry
