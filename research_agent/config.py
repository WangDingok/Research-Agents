"""Configuration classes with inheritance for all modules.

Usage:
    from research_agent.config import config
    
    # Access any config
    config.model.provider          # "azure_openai"
    config.etsy.api_key            # Etsy API key
    config.google.serpapi_key      # SerpAPI key
    config.project_root            # Project root path
    config.charts_dir              # Charts output directory
"""

import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class BaseConfig:
    """Base configuration with common parameters shared across all modules."""
    
    project_root: Path = _PROJECT_ROOT
    data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "output")
    charts_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "public" / "charts")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    current_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelConfig(BaseConfig):
    """LLM model configuration."""
    
    provider: str = field(default_factory=lambda: os.getenv("MODEL_PROVIDER", "azure_openai"))
    temperature: float = 0.0
    max_retries: int = 3
    
    # Azure OpenAI
    azure_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", ""))
    azure_api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_api_version: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", ""))
    
    # Google GenAI
    google_model: str = field(default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))


@dataclass
class EtsyConfig(BaseConfig):
    """Etsy API configuration."""
    
    api_key: str = field(default_factory=lambda: os.getenv("ETSY_API_KEY", ""))
    base_url: str = "https://openapi.etsy.com/v3/application/listings/active"
    etsy_data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "output" / "etsy_data")
    taxonomy_ids: list = field(default_factory=lambda: [449, 482, 559])

    def __post_init__(self):
        super().__post_init__()
        self.etsy_data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)


@dataclass
class GoogleConfig(BaseConfig):
    """Google Search & Trends configuration (SerpAPI)."""
    
    serpapi_key: str = field(default_factory=lambda: os.getenv("SERPAPI_API_KEY", ""))

    @property
    def is_available(self) -> bool:
        return bool(self.serpapi_key)


@dataclass
class TavilyConfig(BaseConfig):
    """Tavily search configuration."""
    
    api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)


@dataclass
class RedditConfig(BaseConfig):
    """Reddit API configuration."""
    
    client_id: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    user_agent: str = field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "script:trend-checker:v1.0"))

    @property
    def is_available(self) -> bool:
        return bool(self.client_id and self.client_secret)


@dataclass
class TikTokConfig(BaseConfig):
    """TikTok API configuration."""
    
    ms_token: str = field(default_factory=lambda: os.getenv("TIKTOK_MS_TOKEN", ""))

    @property
    def is_available(self) -> bool:
        return bool(self.ms_token)


@dataclass
class TwitterConfig(BaseConfig):
    """Twitter scraping configuration."""
    
    base_url: str = "https://www.twitter-trending.com"

    @property
    def is_available(self) -> bool:
        return True  # No API key needed, scraping-based


@dataclass
class AppConfig:
    """Root configuration aggregating all module configs.
    
    Usage:
        config = AppConfig()
        config.model.provider
        config.etsy.api_key
        config.google.serpapi_key
    """
    
    model: ModelConfig = field(default_factory=ModelConfig)
    etsy: EtsyConfig = field(default_factory=EtsyConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    tavily: TavilyConfig = field(default_factory=TavilyConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    tiktok: TikTokConfig = field(default_factory=TikTokConfig)
    twitter: TwitterConfig = field(default_factory=TwitterConfig)
    
    @property
    def project_root(self) -> Path:
        return self.model.project_root
    
    @property
    def charts_dir(self) -> Path:
        return self.model.charts_dir
    
    @property
    def current_date(self) -> str:
        return self.model.current_date


# Singleton instance — import this from anywhere
config = AppConfig()
